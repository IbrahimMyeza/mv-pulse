from collections import Counter
from datetime import datetime, timedelta

from database import db
from models.thread_summary import ThreadSummary
from models.video import Video
from models.voice_insight import VoiceInsight
from models.voice_reply import VoiceReply


def _summary_text(video, replies, topic_label):
    if not replies:
        return f"{video.title} has not built a voice thread yet."
    latest = replies[-1].transcript or replies[-1].video.caption if replies[-1].video else replies[-1].transcript or ""
    lead = latest.strip()[:120]
    if lead:
        return f"Debate around {topic_label} is centering on: {lead}{'...' if len(lead) == 120 else ''}"
    return f"Participants are actively debating {topic_label} in this thread."


def refresh_thread_summary(video_id, root_reply_id=None):
    video = Video.query.get(video_id)
    if not video:
        return None

    replies = VoiceReply.query.filter_by(video_id=video_id).order_by(VoiceReply.created_at.asc()).all()
    if root_reply_id:
        by_parent = {}
        for reply in replies:
            by_parent.setdefault(reply.parent_reply_id, []).append(reply)
        allowed = []
        stack = [root_reply_id]
        seen = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            match = next((reply for reply in replies if reply.id == current), None)
            if match:
                allowed.append(match)
            stack.extend(child.id for child in by_parent.get(current, []))
        replies = allowed

    now = datetime.utcnow()
    recent_window = now - timedelta(hours=6)
    participants = {reply.user_id for reply in replies}
    recent_replies = [reply for reply in replies if (reply.created_at or now) >= recent_window]
    insights = VoiceInsight.query.filter(VoiceInsight.voice_reply_id.in_([reply.id for reply in replies])).all() if replies else []
    topic_counts = Counter(insight.topic_label for insight in insights if insight.topic_label)
    dominant_topic = topic_counts.most_common(1)[0][0] if topic_counts else video.topic or "general"
    controversy = round(max([video.debate_score] + [insight.controversy_score for insight in insights] or [0.0]), 2)
    velocity = round(len(recent_replies) / 6.0, 2) if recent_replies else 0.0
    summary_text = _summary_text(video, replies, dominant_topic)

    summary = ThreadSummary.query.filter_by(video_id=video_id, root_reply_id=root_reply_id).first()
    if not summary:
        summary = ThreadSummary(video_id=video_id, root_reply_id=root_reply_id)
        db.session.add(summary)

    summary.summary_text = summary_text
    summary.cluster_label = dominant_topic
    summary.controversy_score = controversy
    summary.reply_velocity = velocity
    summary.participant_count = len(participants)
    summary.last_computed_at = now
    db.session.commit()
    return summary


def get_thread_summary(video_id, root_reply_id=None):
    summary = ThreadSummary.query.filter_by(video_id=video_id, root_reply_id=root_reply_id).first()
    if not summary:
        summary = refresh_thread_summary(video_id, root_reply_id=root_reply_id)
    if not summary:
        return None
    return serialize_thread_summary(summary)


def serialize_thread_summary(summary):
    return {
        "id": summary.id,
        "video_id": summary.video_id,
        "root_reply_id": summary.root_reply_id,
        "summary_text": summary.summary_text,
        "cluster_label": summary.cluster_label,
        "controversy_score": round(summary.controversy_score, 2),
        "reply_velocity": round(summary.reply_velocity, 2),
        "participant_count": summary.participant_count,
        "last_computed_at": summary.last_computed_at.isoformat() if summary.last_computed_at else None,
    }


def search_discovery(query=None, topic=None, tone=None, limit=12):
    summaries = ThreadSummary.query.order_by(ThreadSummary.last_computed_at.desc()).all()
    tokens = (query or "").lower().split()
    tone = (tone or "").lower().strip()
    topic = (topic or "").lower().strip()
    results = []

    for summary in summaries:
        text = f"{summary.summary_text} {summary.cluster_label}".lower()
        if topic and summary.cluster_label.lower() != topic:
            continue
        score = 0
        if tokens:
            score += sum(1 for token in tokens if token in text)
        if topic and topic in text:
            score += 2
        top_tone = None
        top_insight = (
            VoiceInsight.query.join(VoiceReply, VoiceReply.id == VoiceInsight.voice_reply_id)
            .filter(VoiceReply.video_id == summary.video_id)
            .order_by(VoiceInsight.intelligence_score.desc())
            .first()
        )
        if top_insight:
            top_tone = top_insight.tone_label
        if tone and top_tone != tone:
            continue
        score += 1 if top_tone else 0
        if score <= 0 and (query or topic or tone):
            continue
        results.append({
            "video_id": summary.video_id,
            "summary_text": summary.summary_text,
            "cluster_label": summary.cluster_label,
            "tone_label": top_tone,
            "controversy_score": summary.controversy_score,
            "target_url": f"/video/{summary.video_id}",
            "score": score + summary.controversy_score + summary.reply_velocity,
        })

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]
