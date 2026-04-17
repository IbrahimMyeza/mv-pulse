from collections import Counter

from models.voice_insight import VoiceInsight
from models.voice_reply import VoiceReply


def _speaking_style(avg_sentiment, avg_toxicity, avg_energy, dominant_tone):
    styles = []
    if avg_toxicity >= 0.45:
        styles.append("confrontational")
    elif dominant_tone in {"analytical", "balanced"}:
        styles.append("analytical")
    if avg_energy >= 0.65:
        styles.append("animated")
    elif avg_energy <= 0.3:
        styles.append("calm")
    if dominant_tone == "humorous":
        styles.append("humorous")
    if avg_sentiment >= 0.35:
        styles.append("optimistic")
    return styles or [dominant_tone or "balanced"]


def voice_identity_payload(user, limit=30):
    if not user:
        return {
            "dominant_topics": [],
            "dominant_tone": "balanced",
            "speaking_style": ["balanced"],
            "average_sentiment": 0.0,
            "average_toxicity": 0.0,
            "total_processed_replies": 0,
            "creator_brand_voice_hint": "Voice identity will appear after published replies are processed.",
            "best_performing_replies": [],
            "audience_sentiment_analysis": "Not enough processed replies yet.",
            "suggested_premium_room_topics": [],
        }

    rows = (
        VoiceInsight.query.join(VoiceReply, VoiceReply.id == VoiceInsight.voice_reply_id)
        .filter(VoiceInsight.user_id == user.id, VoiceInsight.processing_state.in_(["complete", "partial"]))
        .order_by(VoiceInsight.updated_at.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        return {
            "dominant_topics": [],
            "dominant_tone": "balanced",
            "speaking_style": ["balanced"],
            "average_sentiment": 0.0,
            "average_toxicity": 0.0,
            "total_processed_replies": 0,
            "creator_brand_voice_hint": "Voice identity will appear after published replies are processed.",
            "best_performing_replies": [],
            "audience_sentiment_analysis": "Not enough processed replies yet.",
            "suggested_premium_room_topics": [],
        }

    topic_counts = Counter(row.topic_label for row in rows if row.topic_label)
    tone_counts = Counter(row.tone_label for row in rows if row.tone_label)
    avg_sentiment = round(sum(row.sentiment_score for row in rows) / len(rows), 2)
    avg_toxicity = round(sum(row.toxicity_score for row in rows) / len(rows), 2)
    avg_energy = round(sum(row.energy_score for row in rows) / len(rows), 2)
    dominant_tone = tone_counts.most_common(1)[0][0] if tone_counts else "balanced"
    best_replies = sorted(rows, key=lambda item: item.intelligence_score, reverse=True)[:3]
    suggested_topics = [topic for topic, _ in topic_counts.most_common(3)]
    brand_voice_hint = f"Known for a {dominant_tone} voice with {', '.join(_speaking_style(avg_sentiment, avg_toxicity, avg_energy, dominant_tone)[:2])} delivery."
    audience_sentiment = (
        "Audience conversations skew positive and high-energy."
        if avg_sentiment >= 0.2 and avg_energy >= 0.45
        else "Audience conversations skew tense or mixed."
        if avg_toxicity >= 0.25 or avg_sentiment <= -0.1
        else "Audience conversations are balanced and steady."
    )

    return {
        "dominant_topics": [{"label": label, "count": count} for label, count in topic_counts.most_common(5)],
        "dominant_tone": dominant_tone,
        "speaking_style": _speaking_style(avg_sentiment, avg_toxicity, avg_energy, dominant_tone),
        "average_sentiment": avg_sentiment,
        "average_toxicity": avg_toxicity,
        "total_processed_replies": len(rows),
        "creator_brand_voice_hint": brand_voice_hint,
        "best_performing_replies": [
            {
                "reply_id": row.voice_reply_id,
                "video_id": row.voice_reply.video_id if row.voice_reply else None,
                "topic_label": row.topic_label,
                "tone_label": row.tone_label,
                "intelligence_score": row.intelligence_score,
                "target_url": f"/video/{row.voice_reply.video_id}?focus_reply_id={row.voice_reply_id}#reply-{row.voice_reply_id}" if row.voice_reply else "/feed",
            }
            for row in best_replies
        ],
        "audience_sentiment_analysis": audience_sentiment,
        "suggested_premium_room_topics": suggested_topics,
    }
