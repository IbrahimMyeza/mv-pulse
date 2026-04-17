from collections import defaultdict
from datetime import datetime, timedelta

from database import db
from models.follow import Follow
from models.like import Like
from models.notification import Notification
from models.save import Save
from models.thread_summary import ThreadSummary
from models.video import Video
from models.voice_insight import VoiceInsight
from models.voice_reply import VoiceReply
from sqlalchemy import func


def reply_target_url(video_id, reply_id):
    if not video_id:
        return "/feed"
    if reply_id:
        return f"/video/{video_id}#reply-{reply_id}"
    return f"/video/{video_id}"


def notification_target_url(notification):
    if notification.video_id or notification.voice_reply_id:
        return reply_target_url(notification.video_id, notification.voice_reply_id)
    if notification.actor:
        return f"/profile/{notification.actor.username}"
    return "/notifications"


def serialize_notification_timeline_item(notification):
    return {
        "id": notification.id,
        "kind": notification.kind,
        "message": notification.message,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
        "actor": notification.actor.username if notification.actor else None,
        "video_id": notification.video_id,
        "voice_reply_id": notification.voice_reply_id,
        "target_url": notification_target_url(notification),
    }


def group_notifications(notifications):
    now = datetime.utcnow()
    today_cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_cutoff = today_cutoff - timedelta(days=6)
    groups = {"today": [], "this_week": [], "older": []}

    for notification in notifications:
        created_at = notification.created_at or now
        item = serialize_notification_timeline_item(notification)
        if created_at >= today_cutoff:
            groups["today"].append(item)
        elif created_at >= week_cutoff:
            groups["this_week"].append(item)
        else:
            groups["older"].append(item)

    return groups


def unread_notification_count(user):
    if not user:
        return 0
    return Notification.query.filter_by(recipient_user_id=user.id, is_read=False).count()


def mark_notifications_read(user, notification_ids=None):
    query = Notification.query.filter_by(recipient_user_id=user.id, is_read=False)
    if notification_ids:
        query = query.filter(Notification.id.in_(notification_ids))

    notifications = query.all()
    for notification in notifications:
        notification.is_read = True

    if notifications:
        from database import db

        db.session.commit()

    return unread_notification_count(user)


def _serialize_video_library_item(video, timestamp=None):
    creator_username = video.creator.username if video.creator else None
    creator_name = creator_username or "Umbono Wami"
    return {
        "id": video.id,
        "title": video.title,
        "caption": video.caption or "",
        "creator": creator_name,
        "creator_username": creator_username,
        "region": video.region,
        "topic": video.topic,
        "likes": video.likes,
        "voice_replies": video.voice_replies,
        "saved_at": timestamp.isoformat() if timestamp else None,
        "target_url": f"/video/{video.id}",
    }


def _serialize_reply_library_item(reply, timestamp=None):
    username = reply.creator.username if reply.creator else "voice"
    video_title = reply.video.title if reply.video else "Video"
    return {
        "id": reply.id,
        "video_id": reply.video_id,
        "username": username,
        "video_title": video_title,
        "transcript": reply.transcript or "Voice note with no transcript yet.",
        "audio_url": reply.audio_url,
        "likes_count": reply.likes_count,
        "saved_at": timestamp.isoformat() if timestamp else None,
        "created_at": (reply.created_at or timestamp).isoformat() if (reply.created_at or timestamp) else None,
        "target_url": reply_target_url(reply.video_id, reply.id),
    }


def load_saved_videos(user):
    saves = Save.query.filter_by(user_id=user.id).filter(Save.video_id.isnot(None)).order_by(Save.created_at.desc()).all()
    video_ids = [item.video_id for item in saves]
    videos = {video.id: video for video in Video.query.filter(Video.id.in_(video_ids)).all()} if video_ids else {}
    return [_serialize_video_library_item(videos[item.video_id], timestamp=item.created_at) for item in saves if item.video_id in videos]


def load_saved_replies(user):
    saves = Save.query.filter_by(user_id=user.id).filter(Save.voice_reply_id.isnot(None)).order_by(Save.created_at.desc()).all()
    reply_ids = [item.voice_reply_id for item in saves]
    replies = {reply.id: reply for reply in VoiceReply.query.filter(VoiceReply.id.in_(reply_ids)).all()} if reply_ids else {}
    return [_serialize_reply_library_item(replies[item.voice_reply_id], timestamp=item.created_at) for item in saves if item.voice_reply_id in replies]


def load_my_voice_replies(user):
    replies = VoiceReply.query.filter_by(user_id=user.id).order_by(VoiceReply.created_at.desc()).all()
    return [_serialize_reply_library_item(reply, timestamp=reply.created_at) for reply in replies]


def load_liked_videos(user):
    likes = Like.query.filter_by(user_id=user.id).filter(Like.video_id.isnot(None)).order_by(Like.created_at.desc()).all()
    video_ids = [item.video_id for item in likes]
    videos = {video.id: video for video in Video.query.filter(Video.id.in_(video_ids)).all()} if video_ids else {}
    return [_serialize_video_library_item(videos[item.video_id], timestamp=item.created_at) for item in likes if item.video_id in videos]


def load_activity(user):
    items = []

    for video in Video.query.filter_by(creator_id=user.id).order_by(Video.created_at.desc()).limit(12).all():
        items.append({
            "kind": "upload",
            "title": f"You posted {video.title}",
            "created_at": video.created_at.isoformat() if video.created_at else None,
            "target_url": f"/video/{video.id}",
        })

    for reply in VoiceReply.query.filter_by(user_id=user.id).order_by(VoiceReply.created_at.desc()).limit(12).all():
        items.append({
            "kind": "voice_reply",
            "title": f"You replied on {reply.video.title if reply.video else 'a video'}",
            "created_at": reply.created_at.isoformat() if reply.created_at else None,
            "target_url": reply_target_url(reply.video_id, reply.id),
        })

    for save in Save.query.filter_by(user_id=user.id).order_by(Save.created_at.desc()).limit(12).all():
        if save.video_id and save.video:
            items.append({
                "kind": "save_video",
                "title": f"You saved {save.video.title}",
                "created_at": save.created_at.isoformat() if save.created_at else None,
                "target_url": f"/video/{save.video_id}",
            })
        elif save.voice_reply_id and save.voice_reply:
            items.append({
                "kind": "save_reply",
                "title": "You saved a voice reply",
                "created_at": save.created_at.isoformat() if save.created_at else None,
                "target_url": reply_target_url(save.voice_reply.video_id if save.voice_reply else None, save.voice_reply_id),
            })

    for like in Like.query.filter_by(user_id=user.id).order_by(Like.created_at.desc()).limit(12).all():
        if like.video_id and like.video:
            items.append({
                "kind": "like_video",
                "title": f"You liked {like.video.title}",
                "created_at": like.created_at.isoformat() if like.created_at else None,
                "target_url": f"/video/{like.video_id}",
            })
        elif like.voice_reply_id and like.voice_reply:
            items.append({
                "kind": "like_reply",
                "title": "You liked a voice reply",
                "created_at": like.created_at.isoformat() if like.created_at else None,
                "target_url": reply_target_url(like.voice_reply.video_id if like.voice_reply else None, like.voice_reply_id),
            })

    return sorted(items, key=lambda item: item["created_at"] or "", reverse=True)[:30]


def _followed_creator_ids(viewer, videos):
    creator_ids = [video.creator_id for video in videos if video.creator_id]
    if not viewer or not creator_ids:
        return set()
    rows = Follow.query.filter(Follow.follower_id == viewer.id, Follow.followed_id.in_(creator_ids)).with_entities(Follow.followed_id).all()
    return {creator_id for (creator_id,) in rows}


def _save_count_map(video_ids):
    counts = defaultdict(int)
    if not video_ids:
        return counts
    rows = Save.query.filter(Save.video_id.in_(video_ids)).all()
    for row in rows:
        counts[row.video_id] += 1
    return counts


def _reply_metrics(video_ids):
    voice_reply_counts = defaultdict(int)
    reply_depth = defaultdict(int)
    if not video_ids:
        return voice_reply_counts, reply_depth

    replies = VoiceReply.query.filter(VoiceReply.video_id.in_(video_ids)).all()
    parent_map = {reply.id: reply.parent_reply_id for reply in replies}

    def depth(reply_id, memo):
        if reply_id in memo:
            return memo[reply_id]
        parent_id = parent_map.get(reply_id)
        if not parent_id:
            memo[reply_id] = 1
        else:
            memo[reply_id] = depth(parent_id, memo) + 1 if parent_id in parent_map else 1
        return memo[reply_id]

    memo = {}
    for reply in replies:
        voice_reply_counts[reply.video_id] += 1
        reply_depth[reply.video_id] = max(reply_depth[reply.video_id], depth(reply.id, memo))

    return voice_reply_counts, reply_depth


def retention_rank_videos(videos, viewer=None):
    if not videos:
        return []

    now = datetime.utcnow()
    followed_ids = _followed_creator_ids(viewer, videos)
    video_ids = [video.id for video in videos]
    save_counts = _save_count_map(video_ids)
    voice_reply_counts, reply_depth = _reply_metrics(video_ids)
    summary_rows = ThreadSummary.query.filter(ThreadSummary.video_id.in_(video_ids), ThreadSummary.root_reply_id.is_(None)).all() if video_ids else []
    summary_map = {row.video_id: row for row in summary_rows}
    insight_rows = (
        db.session.query(
            VoiceReply.video_id,
            func.avg(VoiceInsight.intelligence_score),
            func.avg(VoiceInsight.toxicity_score),
            func.max(VoiceInsight.sentiment_score),
            func.max(VoiceInsight.replay_signal),
        )
        .join(VoiceReply, VoiceReply.id == VoiceInsight.voice_reply_id)
        .filter(VoiceReply.video_id.in_(video_ids))
        .group_by(VoiceReply.video_id)
        .all()
    ) if video_ids else []
    insight_map = {
        video_id: {
            "avg_intelligence": float(avg_intelligence or 0.0),
            "avg_toxicity": float(avg_toxicity or 0.0),
            "max_sentiment": float(max_sentiment or 0.0),
            "max_replay": float(max_replay or 0.0),
        }
        for video_id, avg_intelligence, avg_toxicity, max_sentiment, max_replay in insight_rows
    }

    scored = []
    for video in videos:
        age_hours = max((now - (video.created_at or now)).total_seconds() / 3600, 0)
        freshness_decay = max(0.0, 1.0 - (age_hours / 72.0))
        follow_weight = 1 if viewer and video.creator_id in followed_ids else 0
        save_weight = save_counts.get(video.id, 0)
        voice_reply_weight = voice_reply_counts.get(video.id, video.voice_replies or 0)
        depth_weight = reply_depth.get(video.id, 0)
        summary = summary_map.get(video.id)
        insight = insight_map.get(video.id, {})
        intelligence_score = float(insight.get("avg_intelligence", 0.0))
        controversy_boost = float(summary.controversy_score if summary else 0.0)
        velocity_boost = float(summary.reply_velocity if summary else 0.0)
        sentiment_boost = abs(float(insight.get("max_sentiment", 0.0)))
        replay_boost = float(insight.get("max_replay", 0.0))
        moderation_penalty = 2.5 if float(insight.get("avg_toxicity", 0.0)) >= 0.72 else 1.25 if float(insight.get("avg_toxicity", 0.0)) >= 0.45 else 0.0
        retention_score = (
            (follow_weight * 3)
            + (save_weight * 4)
            + (voice_reply_weight * 5)
            + (depth_weight * 2)
            + freshness_decay
            + (getattr(video, "thread_heat_score", 0) * 1.5)
            + controversy_boost
            + velocity_boost
            + sentiment_boost
            + replay_boost
            + (intelligence_score * 1.5)
            - moderation_penalty
        )
        video.retention_score = round(retention_score, 2)
        video.intelligence_score = round(intelligence_score, 2)
        scored.append((retention_score, video.created_at or now, video))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [video for _, _, video in scored]