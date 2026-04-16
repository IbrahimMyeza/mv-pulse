import os
from collections import Counter

from flask import session
from sqlalchemy import func
from werkzeug.utils import secure_filename

from database import db
from ml.debate_detector import controversy_score
from ml.ranker import rank_reels
from ml.reputation import get_creator_score, update_creator_score
from models.export_project import ExportProject
from models.follow import Follow
from models.like import Like
from models.notification import Notification
from models.reel import Reel
from models.save import Save
from models.user import User
from models.user_social_profile import UserSocialProfile
from models.video import Video
from models.voice_reply import VoiceReply
from services.social_retention import group_notifications, retention_rank_videos, unread_notification_count
from services.thread_heat import compute_hot_threads, inject_hot_thread_cards, notify_hot_thread_participants

SUPPORTED_LANGUAGES = {
    "en": "English",
    "zu": "isiZulu",
}

UI_COPY = {
    "feed_title": {"en": "For You", "zu": "Okwakho"},
    "reply_label": {"en": "Voice replies", "zu": "Izimpendulo zezwi"},
    "upload_label": {"en": "Upload", "zu": "Layisha"},
}


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def ensure_social_seed():
    if Video.query.count() > 0:
        return

    legacy_reels = Reel.query.order_by(Reel.id.asc()).all()
    for reel in legacy_reels:
        video = Video(
            title=reel.title,
            caption=f"{reel.region} is reacting to {reel.topic} right now.",
            description=f"Legacy MV Pulse reel imported into Umbono Wami social feed.",
            video_path=reel.video_path,
            topic=getattr(reel, "topic", "general") or "general",
            region=getattr(reel, "region", "Durban") or "Durban",
            category=getattr(reel, "category", "general") or "general",
            likes=getattr(reel, "likes", 0),
            views=getattr(reel, "views", 0),
            comments=getattr(reel, "comments", 0),
            watch_time=getattr(reel, "watch_time", 0),
            creator_score=getattr(reel, "creator_score", 1.0),
            report_count=getattr(reel, "report_count", 0),
            voice_replies=getattr(reel, "voice_replies", 0),
            emotion_score=getattr(reel, "emotion_score", 1.0),
            debate_score=getattr(reel, "debate_score", 0.0),
            community_score=getattr(reel, "community_score", 1.0),
            transcript_summary=f"Imported from legacy reel: {reel.title}",
        )
        db.session.add(video)

    db.session.commit()


def save_video_file(file_storage, target_folder):
    os.makedirs(target_folder, exist_ok=True)
    filename = secure_filename(file_storage.filename or "upload.bin")
    if not filename:
        filename = "upload.bin"
    file_path = os.path.join(target_folder, filename)
    file_storage.save(file_path)
    return "/" + file_path.replace("\\", "/")


def ensure_social_profile(user):
    if not user:
        return None

    profile = user.social_profile
    if profile:
        return profile

    profile = UserSocialProfile(
        user_id=user.id,
        display_name=user.username,
        bio="Umbono Wami creator profile",
    )
    db.session.add(profile)
    db.session.commit()
    return profile


def serialize_social_profile(profile):
    if not profile:
        return None

    return {
        "display_name": profile.display_name,
        "headline": profile.headline,
        "bio": profile.bio or "",
        "avatar_url": profile.avatar_url,
        "region": profile.region,
        "primary_language_code": profile.primary_language_code,
        "secondary_language_code": profile.secondary_language_code,
        "voice_style": profile.voice_style,
    }


def serialize_user(user):
    if not user:
        return None

    profile = user.social_profile
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "social_profile": serialize_social_profile(profile),
    }


def serialize_video(video):
    creator_username = video.creator.username if video.creator else None
    creator = creator_username or "Umbono Wami"
    return {
        "kind": "video",
        "id": video.id,
        "title": video.title,
        "caption": video.caption or "",
        "description": video.description or "",
        "video_url": video.video_path,
        "thumbnail_url": video.thumbnail_url,
        "topic": video.topic,
        "region": video.region,
        "category": video.category,
        "language_code": video.language_code,
        "language_label": SUPPORTED_LANGUAGES.get(video.language_code, video.language_code),
        "creator": creator,
        "creator_username": creator_username,
        "creator_id": video.creator_id,
        "likes": video.likes,
        "views": video.views,
        "voice_replies": video.voice_replies,
        "saves_count": getattr(video, "saves_count", 0),
        "shares_count": video.shares_count,
        "debate_score": round(video.debate_score, 2),
        "creator_score": round(video.creator_score, 2),
        "for_you_score": round(rank_reels([video])[0] and (video.likes * 2 + video.views + video.voice_replies * 10), 2) if video else 0,
        "is_liked": getattr(video, "is_liked", False),
        "is_saved": getattr(video, "is_saved", False),
        "creator_is_followed": getattr(video, "creator_is_followed", False),
        "can_follow_creator": getattr(video, "can_follow_creator", False),
        "creator_followers_count": getattr(video, "creator_followers_count", 0),
        "retention_score": getattr(video, "retention_score", 0),
        "thread_heat_score": getattr(video, "thread_heat_score", 0),
    }


def serialize_hot_thread_card(card):
    return {
        "kind": "hot_thread",
        "reel_id": card["reel_id"],
        "video_id": card["video_id"],
        "highlighted_reply_id": card["highlighted_reply_id"],
        "heat_score": card["heat_score"],
        "top_participants": card["top_participants"],
        "reply_count": card["reply_count"],
        "last_reply_at": card["last_reply_at"],
        "cta_text": card["cta_text"],
        "target_url": card["target_url"],
        "title": card["title"],
        "caption": card["caption"],
        "creator": card["creator"],
        "reply_depth": card["reply_depth"],
    }


def serialize_notification(item):
    from services.social_retention import serialize_notification_timeline_item

    return serialize_notification_timeline_item(item)


def serialize_voice_reply(reply):
    return {
        "id": reply.id,
        "video_id": reply.video_id,
        "user_id": reply.user_id,
        "username": reply.creator.username if reply.creator else "voice",
        "audio_url": reply.audio_url,
        "duration": reply.duration,
        "transcript": reply.transcript or "",
        "language_code": reply.language_code,
        "likes_count": reply.likes_count,
        "saves_count": getattr(reply, "saves_count", 0),
        "sentiment_score": round(reply.sentiment_score, 2),
        "controversy_score": round(reply.controversy_score, 2),
        "parent_reply_id": reply.parent_reply_id,
        "created_at": reply.created_at.isoformat() if reply.created_at else None,
        "is_liked": getattr(reply, "is_liked", False),
        "is_saved": getattr(reply, "is_saved", False),
        "can_reply": getattr(reply, "can_reply", False),
        "target_url": f"/video/{reply.video_id}#reply-{reply.id}",
        "children": [serialize_voice_reply(child) for child in sorted(reply.child_replies, key=lambda item: item.created_at or 0)],
    }


def _save_counts_for_videos(video_ids):
    if not video_ids:
        return {}

    rows = db.session.query(Save.video_id, func.count(Save.id)).filter(Save.video_id.in_(video_ids)).group_by(Save.video_id).all()
    return {video_id: count for video_id, count in rows}


def _save_counts_for_replies(reply_ids):
    if not reply_ids:
        return {}

    rows = db.session.query(Save.voice_reply_id, func.count(Save.id)).filter(Save.voice_reply_id.in_(reply_ids)).group_by(Save.voice_reply_id).all()
    return {reply_id: count for reply_id, count in rows}


def _liked_video_ids(user, video_ids):
    if not user or not video_ids:
        return set()
    rows = Like.query.filter(Like.user_id == user.id, Like.video_id.in_(video_ids)).with_entities(Like.video_id).all()
    return {video_id for (video_id,) in rows}


def _saved_video_ids(user, video_ids):
    if not user or not video_ids:
        return set()
    rows = Save.query.filter(Save.user_id == user.id, Save.video_id.in_(video_ids)).with_entities(Save.video_id).all()
    return {video_id for (video_id,) in rows}


def _liked_reply_ids(user, reply_ids):
    if not user or not reply_ids:
        return set()
    rows = Like.query.filter(Like.user_id == user.id, Like.voice_reply_id.in_(reply_ids)).with_entities(Like.voice_reply_id).all()
    return {reply_id for (reply_id,) in rows}


def _saved_reply_ids(user, reply_ids):
    if not user or not reply_ids:
        return set()
    rows = Save.query.filter(Save.user_id == user.id, Save.voice_reply_id.in_(reply_ids)).with_entities(Save.voice_reply_id).all()
    return {reply_id for (reply_id,) in rows}


def _followed_user_ids(user, creator_ids):
    if not user or not creator_ids:
        return set()
    rows = Follow.query.filter(Follow.follower_id == user.id, Follow.followed_id.in_(creator_ids)).with_entities(Follow.followed_id).all()
    return {followed_id for (followed_id,) in rows}


def _follower_counts(creator_ids):
    if not creator_ids:
        return {}
    rows = db.session.query(Follow.followed_id, func.count(Follow.id)).filter(Follow.followed_id.in_(creator_ids)).group_by(Follow.followed_id).all()
    return {creator_id: count for creator_id, count in rows}


def hydrate_videos(videos, viewer=None):
    video_ids = [video.id for video in videos]
    creator_ids = [video.creator_id for video in videos if video.creator_id]
    saved_counts = _save_counts_for_videos(video_ids)
    liked_ids = _liked_video_ids(viewer, video_ids)
    saved_ids = _saved_video_ids(viewer, video_ids)
    followed_ids = _followed_user_ids(viewer, creator_ids)
    follower_counts = _follower_counts(creator_ids)

    for video in videos:
        video.saves_count = saved_counts.get(video.id, 0)
        video.is_liked = video.id in liked_ids
        video.is_saved = video.id in saved_ids
        video.creator_is_followed = bool(viewer and video.creator_id and video.creator_id in followed_ids and viewer.id != video.creator_id)
        video.can_follow_creator = bool(video.creator_id and (not viewer or viewer.id != video.creator_id))
        video.creator_followers_count = follower_counts.get(video.creator_id, 0)
    return videos


def _hydrate_replies(replies, viewer=None):
    reply_ids = []

    def collect(items):
        for item in items:
            reply_ids.append(item.id)
            collect(item.child_replies)

    collect(replies)
    saved_counts = _save_counts_for_replies(reply_ids)
    liked_ids = _liked_reply_ids(viewer, reply_ids)
    saved_ids = _saved_reply_ids(viewer, reply_ids)

    def apply_state(items):
        for item in items:
            item.saves_count = saved_counts.get(item.id, 0)
            item.is_liked = item.id in liked_ids
            item.is_saved = item.id in saved_ids
            item.can_reply = viewer is not None
            apply_state(item.child_replies)

    apply_state(replies)
    return replies


def build_reply_tree(video_id, viewer=None):
    replies = VoiceReply.query.filter_by(video_id=video_id).order_by(VoiceReply.created_at.asc()).all()
    top_level = [reply for reply in replies if reply.parent_reply_id is None]
    _hydrate_replies(top_level, viewer=viewer)
    return [serialize_voice_reply(reply) for reply in top_level]


def create_notification(recipient_id, kind, message, actor_id=None, video_id=None, voice_reply_id=None):
    if not recipient_id:
        return None

    notification = Notification(
        recipient_user_id=recipient_id,
        actor_user_id=actor_id,
        video_id=video_id,
        voice_reply_id=voice_reply_id,
        kind=kind,
        message=message,
    )
    db.session.add(notification)
    db.session.commit()
    return notification


def interaction_snapshot(user, video=None, voice_reply=None, reel=None):
    if not user:
        return {"liked": False, "saved": False}

    like_query = Like.query.filter_by(user_id=user.id)
    save_query = Save.query.filter_by(user_id=user.id)

    if video:
        like_query = like_query.filter_by(video_id=video.id)
        save_query = save_query.filter_by(video_id=video.id)
    elif voice_reply:
        like_query = like_query.filter_by(voice_reply_id=voice_reply.id)
        save_query = save_query.filter_by(voice_reply_id=voice_reply.id)
    elif reel:
        like_query = like_query.filter_by(reel_id=reel.id)
        save_query = save_query.filter_by(reel_id=reel.id)

    return {
        "liked": like_query.first() is not None,
        "saved": save_query.first() is not None,
    }


def follow_state(viewer, profile_user):
    if not viewer or not profile_user or viewer.id == profile_user.id:
        return False
    return Follow.query.filter_by(follower_id=viewer.id, followed_id=profile_user.id).first() is not None


def ranked_feed(preferred_topic=None, preferred_region=None, viewer=None):
    ensure_social_seed()
    videos = Video.query.filter_by(is_public=True).order_by(Video.created_at.desc()).all()
    baseline = rank_reels(videos, preferred_topic=preferred_topic, preferred_region=preferred_region)
    hot_threads, _ = compute_hot_threads(baseline, viewer=viewer)
    notify_hot_thread_participants(hot_threads)
    ranked_videos = retention_rank_videos(baseline, viewer=viewer)
    return ranked_videos, hot_threads


def preferred_topic_for(user):
    if not user:
        return None
    user_videos = user.videos.all()
    if not user_videos:
        return None
    counts = Counter(video.topic for video in user_videos if video.topic)
    return counts.most_common(1)[0][0] if counts else None


def preferred_region_for(user):
    if not user:
        return None
    user_videos = user.videos.all()
    if not user_videos:
        return None
    counts = Counter(video.region for video in user_videos if video.region)
    return counts.most_common(1)[0][0] if counts else None


def social_context(active_tab="home", profile_user=None, selected_video=None):
    ensure_social_seed()
    user = current_user()
    if user:
        ensure_social_profile(user)
    if profile_user:
        ensure_social_profile(profile_user)
    topic = preferred_topic_for(user)
    region = preferred_region_for(user)
    videos, hot_threads = ranked_feed(preferred_topic=topic, preferred_region=region, viewer=user)
    hydrate_videos(videos, viewer=user)
    feed_items = inject_hot_thread_cards(videos, hot_threads)
    featured_video = selected_video or (videos[0] if videos else None)
    profile_owner = profile_user or user

    saved_projects = []
    if user:
        saved_projects = ExportProject.query.filter_by(user_id=user.id).order_by(ExportProject.created_at.desc()).limit(6).all()

    notifications = []
    if user:
        notification_limit = 50 if active_tab == "notifications" else 12
        notifications = Notification.query.filter_by(recipient_user_id=user.id).order_by(Notification.created_at.desc()).limit(notification_limit).all()
    notification_groups = group_notifications(notifications)

    recent_replies = VoiceReply.query.order_by(VoiceReply.created_at.desc()).limit(10).all()
    recent_replies_serialized = [serialize_voice_reply(reply) for reply in recent_replies]
    follower_count = profile_owner.followers.count() if profile_owner else 0
    following_count = profile_owner.following.count() if profile_owner else 0
    video_count = profile_owner.videos.count() if profile_owner else 0
    reply_count = profile_owner.voice_replies.count() if profile_owner else 0

    return {
        "active_tab": active_tab,
        "current_user": user,
        "current_user_payload": serialize_user(user),
        "feed_videos": [serialize_video(video) for video in videos],
        "feed_items": [serialize_video(item["payload"]) if item["kind"] == "video" else serialize_hot_thread_card(item["payload"]) for item in feed_items],
        "hot_threads": [serialize_hot_thread_card(card) for card in hot_threads],
        "featured_video": serialize_video(featured_video) if featured_video else None,
        "selected_reply_threads": build_reply_tree(featured_video.id, viewer=user) if featured_video else [],
        "notifications": [serialize_notification(item) for item in notifications],
        "notification_groups": notification_groups,
        "notifications_unread_count": unread_notification_count(user),
        "recent_voice_threads": recent_replies_serialized,
        "profile_user": profile_owner,
        "profile_is_owner": bool(user and profile_owner and user.id == profile_owner.id),
        "profile_stats": {
            "followers": follower_count,
            "following": following_count,
            "videos": video_count,
            "replies": reply_count,
            "creator_score": round(get_creator_score(profile_owner.id if profile_owner else 0), 2) if profile_owner else 100,
        },
        "profile_videos": [serialize_video(video) for video in (profile_owner.videos.order_by(Video.created_at.desc()).all() if profile_owner else [])],
        "saved_projects": [
            {
                "id": project.id,
                "title": project.title,
                "kind": project.kind,
                "status": project.status,
            }
            for project in saved_projects
        ],
        "locale_options": SUPPORTED_LANGUAGES,
        "ui_copy": UI_COPY,
        "is_following_profile": follow_state(user, profile_owner),
    }


def touch_video_reputation(video, sentiment_score=0.0):
    creator_id = video.creator_id or 0
    creator_score = update_creator_score(creator_id, video.likes + video.voice_replies + sentiment_score)
    video.creator_score = max(video.creator_score, creator_score * 0.01)
    db.session.commit()
