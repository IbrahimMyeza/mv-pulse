from collections import Counter, defaultdict
from datetime import datetime, timedelta

from database import db
from models.follow import Follow
from models.notification import Notification
from models.save import Save
from models.voice_reply import VoiceReply
from sqlalchemy import func

REPLY_LISTEN_COUNTS = defaultdict(int)
HOT_THREAD_INJECTION_FREQUENCY = 3
HOT_THREAD_MIN_SCORE = 12


def record_reply_listen(reply_id):
    REPLY_LISTEN_COUNTS[int(reply_id)] += 1
    return REPLY_LISTEN_COUNTS[int(reply_id)]


def _reply_depth(reply, cache):
    if reply.id in cache:
        return cache[reply.id]
    if not reply.parent_reply_id:
        cache[reply.id] = 1
        return 1
    if not reply.parent_reply:
        cache[reply.id] = 1
        return 1
    cache[reply.id] = _reply_depth(reply.parent_reply, cache) + 1
    return cache[reply.id]


def _participant_payload(counter):
    participants = []
    for username, count in counter.most_common(3):
        participants.append({
            "username": username,
            "initials": "".join(part[0].upper() for part in username.split("_") if part)[:2] or username[:2].upper(),
            "count": count,
        })
    return participants


def _target_url(video_id, reply_id):
    if reply_id:
        return f"/video/{video_id}?focus_reply_id={reply_id}#reply-{reply_id}"
    return f"/video/{video_id}"


def _cta_text(new_replies, unique_speakers, last_hour_replies):
    if last_hour_replies >= 3 and unique_speakers >= 3:
        return f"{unique_speakers} creators replied in the last hour"
    if new_replies >= 2:
        return "People are talking about this right now 🎙️"
    return "This voice debate is trending"


def _follow_overlap(creator_id, participant_ids):
    if not creator_id or not participant_ids:
        return 0
    return Follow.query.filter(Follow.followed_id == creator_id, Follow.follower_id.in_(participant_ids)).count()


def _saves_map(video_ids):
    if not video_ids:
        return {}
    rows = db.session.query(Save.video_id, func.count(Save.id)).filter(Save.video_id.in_(video_ids)).group_by(Save.video_id).all()
    return {video_id: count for video_id, count in rows}


def _notification_exists(user_id, video_id, recent_cutoff):
    return Notification.query.filter(
        Notification.recipient_user_id == user_id,
        Notification.kind == "thread_trending",
        Notification.video_id == video_id,
        Notification.created_at >= recent_cutoff,
    ).first() is not None


def compute_hot_threads(videos, viewer=None):
    if not videos:
        return [], {}

    now = datetime.utcnow()
    recent_cutoff = now - timedelta(hours=6)
    hour_cutoff = now - timedelta(hours=1)
    video_ids = [video.id for video in videos]
    replies = VoiceReply.query.filter(VoiceReply.video_id.in_(video_ids)).order_by(VoiceReply.created_at.desc()).all()
    replies_by_video = defaultdict(list)
    for reply in replies:
        replies_by_video[reply.video_id].append(reply)

    saves_by_video = _saves_map(video_ids)
    hot_threads = []
    heat_by_video = {}

    for video in videos:
        thread_replies = replies_by_video.get(video.id, [])
        if not thread_replies:
            video.thread_heat_score = 0
            continue

        recent_replies = [reply for reply in thread_replies if (reply.created_at or now) >= recent_cutoff]
        recent_hour_replies = [reply for reply in thread_replies if (reply.created_at or now) >= hour_cutoff]
        participant_ids = {reply.user_id for reply in thread_replies}
        participant_names = Counter(reply.creator.username if reply.creator else "voice" for reply in recent_replies or thread_replies)
        depth_cache = {}
        deepest_reply = None
        deepest_level = 0
        for reply in thread_replies:
            level = _reply_depth(reply, depth_cache)
            if level >= deepest_level:
                deepest_level = level
                deepest_reply = reply

        highlighted_reply = deepest_reply or thread_replies[0]
        replay_listens = sum(REPLY_LISTEN_COUNTS.get(reply.id, 0) for reply in thread_replies)
        follow_overlap = _follow_overlap(video.creator_id, participant_ids)
        new_replies = len(recent_replies)
        unique_speakers = len(participant_ids)
        saves = saves_by_video.get(video.id, 0)
        heat_score = (
            (new_replies * 5)
            + (deepest_level * 4)
            + (unique_speakers * 3)
            + (replay_listens * 2)
            + (saves * 2)
            + (follow_overlap * 1)
        )
        video.thread_heat_score = heat_score
        heat_by_video[video.id] = heat_score

        if heat_score < HOT_THREAD_MIN_SCORE:
            continue

        hot_threads.append({
            "kind": "hot_thread",
            "reel_id": video.id,
            "video_id": video.id,
            "highlighted_reply_id": highlighted_reply.id if highlighted_reply else None,
            "heat_score": round(heat_score, 2),
            "top_participants": _participant_payload(participant_names),
            "reply_count": len(thread_replies),
            "last_reply_at": (thread_replies[0].created_at.isoformat() if thread_replies and thread_replies[0].created_at else None),
            "cta_text": _cta_text(new_replies, unique_speakers, len(recent_hour_replies)),
            "target_url": _target_url(video.id, highlighted_reply.id if highlighted_reply else None),
            "title": video.title,
            "caption": video.caption or video.description or "Voice debate heating up.",
            "creator": video.creator.username if video.creator else "Umbono Wami",
            "reply_depth": deepest_level,
        })

    hot_threads.sort(key=lambda item: (item["heat_score"], item["last_reply_at"] or ""), reverse=True)
    return hot_threads, heat_by_video


def inject_hot_thread_cards(videos, hot_threads, every_n=HOT_THREAD_INJECTION_FREQUENCY):
    feed_items = []
    injected_reels = set()
    hot_queue = list(hot_threads)

    for index, video in enumerate(videos, start=1):
        feed_items.append({"kind": "video", "payload": video})
        if index % every_n != 0:
            continue

        while hot_queue:
            card = hot_queue.pop(0)
            if card["reel_id"] in injected_reels:
                continue
            injected_reels.add(card["reel_id"])
            feed_items.append({"kind": "hot_thread", "payload": card})
            break

    return feed_items


def notify_hot_thread_participants(hot_threads, replies_by_video=None):
    if not hot_threads:
        return

    cutoff = datetime.utcnow() - timedelta(hours=6)
    pending = []

    for thread in hot_threads:
        video_id = thread["video_id"]
        highlighted_reply_id = thread["highlighted_reply_id"]
        replies = replies_by_video.get(video_id) if replies_by_video else None
        if replies is None:
            replies = VoiceReply.query.filter_by(video_id=video_id).all()

        participant_ids = {reply.user_id for reply in replies}
        for participant_id in participant_ids:
            if _notification_exists(participant_id, video_id, cutoff):
                continue
            pending.append(Notification(
                recipient_user_id=participant_id,
                actor_user_id=None,
                video_id=video_id,
                voice_reply_id=highlighted_reply_id,
                kind="thread_trending",
                message="Your conversation is trending 🎙️",
            ))

    if pending:
        db.session.add_all(pending)
        db.session.commit()