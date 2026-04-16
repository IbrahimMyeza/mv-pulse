from database import db
from models.follow import Follow
from models.like import Like
from models.notification import Notification
from models.save import Save
from models.video import Video
from models.voice_reply import VoiceReply
from routes.social_utils import create_notification


def _delete_notification(recipient_id, actor_id, kind, video_id=None, voice_reply_id=None):
    query = Notification.query.filter_by(
        recipient_user_id=recipient_id,
        actor_user_id=actor_id,
        kind=kind,
    )
    if video_id is not None:
        query = query.filter_by(video_id=video_id)
    if voice_reply_id is not None:
        query = query.filter_by(voice_reply_id=voice_reply_id)

    for notification in query.all():
        db.session.delete(notification)


def toggle_follow(viewer, target_user):
    relation = Follow.query.filter_by(follower_id=viewer.id, followed_id=target_user.id).first()
    if relation:
        db.session.delete(relation)
        _delete_notification(target_user.id, viewer.id, "follow")
        db.session.commit()
        return {
            "following": False,
            "followers": target_user.followers.count(),
            "following_count": viewer.following.count(),
        }

    relation = Follow(follower_id=viewer.id, followed_id=target_user.id)
    db.session.add(relation)
    db.session.commit()
    create_notification(
        recipient_id=target_user.id,
        actor_id=viewer.id,
        kind="follow",
        message=f"{viewer.username} followed you",
    )
    return {
        "following": True,
        "followers": target_user.followers.count(),
        "following_count": viewer.following.count(),
    }


def toggle_video_like(viewer, video):
    like = Like.query.filter_by(user_id=viewer.id, video_id=video.id).first()
    if like:
        db.session.delete(like)
        video.likes = max((video.likes or 0) - 1, 0)
        if video.creator_id and video.creator_id != viewer.id:
            _delete_notification(video.creator_id, viewer.id, "video_like", video_id=video.id)
        db.session.commit()
        return {"liked": False, "likes": video.likes}

    like = Like(user_id=viewer.id, video_id=video.id)
    db.session.add(like)
    video.likes = (video.likes or 0) + 1
    db.session.commit()
    if video.creator_id and video.creator_id != viewer.id:
        create_notification(
            recipient_id=video.creator_id,
            actor_id=viewer.id,
            video_id=video.id,
            kind="video_like",
            message=f"{viewer.username} liked your video",
        )
    return {"liked": True, "likes": video.likes}


def toggle_voice_reply_like(viewer, voice_reply):
    like = Like.query.filter_by(user_id=viewer.id, voice_reply_id=voice_reply.id).first()
    if like:
        db.session.delete(like)
        voice_reply.likes_count = max((voice_reply.likes_count or 0) - 1, 0)
        if voice_reply.user_id != viewer.id:
            _delete_notification(voice_reply.user_id, viewer.id, "voice_reply_like", voice_reply_id=voice_reply.id)
        db.session.commit()
        return {"liked": False, "likes_count": voice_reply.likes_count}

    like = Like(user_id=viewer.id, voice_reply_id=voice_reply.id)
    db.session.add(like)
    voice_reply.likes_count = (voice_reply.likes_count or 0) + 1
    db.session.commit()
    if voice_reply.user_id != viewer.id:
        create_notification(
            recipient_id=voice_reply.user_id,
            actor_id=viewer.id,
            video_id=voice_reply.video_id,
            voice_reply_id=voice_reply.id,
            kind="voice_reply_like",
            message=f"{viewer.username} liked your voice reply",
        )
    return {"liked": True, "likes_count": voice_reply.likes_count}


def toggle_video_save(viewer, video):
    save = Save.query.filter_by(user_id=viewer.id, video_id=video.id).first()
    if save:
        db.session.delete(save)
        db.session.commit()
        saves_count = Save.query.filter_by(video_id=video.id).count()
        return {"saved": False, "saves_count": saves_count}

    save = Save(user_id=viewer.id, video_id=video.id)
    db.session.add(save)
    db.session.commit()
    saves_count = Save.query.filter_by(video_id=video.id).count()
    return {"saved": True, "saves_count": saves_count}


def track_video_share(video):
    video.shares_count = (video.shares_count or 0) + 1
    db.session.commit()
    return {"shares_count": video.shares_count}


def follow_payload(viewer, target_user, state):
    return {
        "target_user_id": target_user.id,
        "username": target_user.username,
        "following": state["following"],
        "followers": state["followers"],
        "following_count": state["following_count"],
        "viewer_id": viewer.id,
    }