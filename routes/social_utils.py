import os
from collections import Counter

from flask import session
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
    creator = video.creator.username if video.creator else "Umbono Wami"
    likes_count = video.likes.count() if hasattr(video, "likes") else video.likes
    saves_count = video.saves.count() if hasattr(video, "saves") else 0
    return {
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
        "creator_id": video.creator_id,
        "likes": likes_count,
        "views": video.views,
        "voice_replies": video.voice_replies,
        "saves_count": saves_count,
        "shares_count": video.shares_count,
        "debate_score": round(video.debate_score, 2),
        "creator_score": round(video.creator_score, 2),
        "for_you_score": round(rank_reels([video])[0] and (video.likes * 2 + video.views + video.voice_replies * 10), 2) if video else 0,
    }


def serialize_notification(item):
    return {
        "id": item.id,
        "kind": item.kind,
        "message": item.message,
        "is_read": item.is_read,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "actor": item.actor.username if item.actor else None,
        "video_id": item.video_id,
    }


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
        "saves_count": reply.saves.count() if hasattr(reply, "saves") else 0,
        "sentiment_score": round(reply.sentiment_score, 2),
        "controversy_score": round(reply.controversy_score, 2),
        "parent_reply_id": reply.parent_reply_id,
        "created_at": reply.created_at.isoformat() if reply.created_at else None,
        "children": [serialize_voice_reply(child) for child in sorted(reply.child_replies, key=lambda item: item.created_at or 0)],
    }


def build_reply_tree(video_id):
    replies = VoiceReply.query.filter_by(video_id=video_id).order_by(VoiceReply.created_at.asc()).all()
    top_level = [reply for reply in replies if reply.parent_reply_id is None]
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


def ranked_feed(preferred_topic=None, preferred_region=None):
    ensure_social_seed()
    videos = Video.query.filter_by(is_public=True).order_by(Video.created_at.desc()).all()
    return rank_reels(videos, preferred_topic=preferred_topic, preferred_region=preferred_region)


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
    topic = preferred_topic_for(user)
    region = preferred_region_for(user)
    videos = ranked_feed(preferred_topic=topic, preferred_region=region)
    featured_video = selected_video or (videos[0] if videos else None)
    profile_owner = profile_user or user

    saved_projects = []
    if user:
        saved_projects = ExportProject.query.filter_by(user_id=user.id).order_by(ExportProject.created_at.desc()).limit(6).all()

    notifications = []
    if user:
        notifications = Notification.query.filter_by(recipient_user_id=user.id).order_by(Notification.created_at.desc()).limit(12).all()

    recent_replies = VoiceReply.query.order_by(VoiceReply.created_at.desc()).limit(10).all()
    recent_replies_serialized = [serialize_voice_reply(reply) for reply in recent_replies]
    follower_count = profile_owner.followers.count() if profile_owner else 0
    following_count = profile_owner.following.count() if profile_owner else 0
    video_count = profile_owner.videos.count() if profile_owner else 0
    reply_count = profile_owner.voice_replies.count() if profile_owner else 0

    return {
        "active_tab": active_tab,
        "current_user": user,
        "feed_videos": [serialize_video(video) for video in videos],
        "featured_video": serialize_video(featured_video) if featured_video else None,
        "selected_reply_threads": build_reply_tree(featured_video.id) if featured_video else [],
        "notifications": [serialize_notification(item) for item in notifications],
        "recent_voice_threads": recent_replies_serialized,
        "profile_user": profile_owner,
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
