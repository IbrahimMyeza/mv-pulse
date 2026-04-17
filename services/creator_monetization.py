from collections import Counter, defaultdict
from datetime import datetime

from database import db
from models.creator_subscription import CreatorSubscription
from models.notification import Notification
from models.premium_voice_room import PremiumVoiceRoom
from models.subscriber_access import SubscriberAccess
from models.tip_transaction import TipTransaction
from models.video import Video
from models.voice_reply import VoiceReply
from models.voice_room_participant import VoiceRoomParticipant

DEFAULT_TIERS = [
    {"tier_name": "Supporter", "monthly_price_cents": 500, "description": "Support the creator and unlock supporter rooms."},
    {"tier_name": "Inner Circle", "monthly_price_cents": 1200, "description": "Closer access to premium voice chains and AMA rooms."},
    {"tier_name": "Debate Club", "monthly_price_cents": 2500, "description": "Priority access to creator-led debate rooms and exclusive reply chains."},
]


def ensure_creator_tiers(creator):
    if creator.creator_subscription_tiers.count() > 0:
        return creator.creator_subscription_tiers.order_by(CreatorSubscription.monthly_price_cents.asc()).all()

    tiers = []
    for index, definition in enumerate(DEFAULT_TIERS):
        tier = CreatorSubscription(
            creator_user_id=creator.id,
            tier_name=definition["tier_name"],
            monthly_price_cents=definition["monthly_price_cents"],
            description=definition["description"],
            founder_badges_enabled=index == 0,
        )
        db.session.add(tier)
        tiers.append(tier)
    db.session.commit()
    return tiers


def active_access_records(user, creator_id=None):
    if not user:
        return []
    now = datetime.utcnow()
    query = SubscriberAccess.query.filter(SubscriberAccess.subscriber_user_id == user.id)
    if creator_id is not None:
        query = query.filter(SubscriberAccess.creator_user_id == creator_id)
    records = query.all()
    return [record for record in records if record.expires_at is None or record.expires_at >= now]


def has_subscription_access(user, creator_id):
    return any(record.access_type == "subscription" for record in active_access_records(user, creator_id=creator_id))


def supporter_badge_for_user(user_id, creator_id):
    record = SubscriberAccess.query.filter_by(subscriber_user_id=user_id, creator_user_id=creator_id, access_type="subscription").order_by(SubscriberAccess.created_at.desc()).first()
    if not record:
        return None
    if record.expires_at and record.expires_at < datetime.utcnow():
        return None
    badge = record.tier_name or "Supporter"
    if record.founder_badge_granted:
        badge = f"Founder · {badge}"
    return badge


def room_target_url(room):
    if room.highlighted_reply_id:
        return f"/video/{room.video_id}?focus_reply_id={room.highlighted_reply_id}#reply-{room.highlighted_reply_id}"
    if room.video_id:
        return f"/video/{room.video_id}"
    return "/feed"


def room_label(room):
    if room.session_kind == "ama":
        return "🎙️ AMA Live Thread"
    if room.room_type == "subscriber_only":
        return "💎 Inner Circle Reply Chain"
    if room.room_type in {"paid_entry", "invite_only"}:
        return "🔒 Premium Debate"
    return "🎙️ Premium Voice Room"


def room_access_state(user, room):
    now = datetime.utcnow()
    participant = VoiceRoomParticipant.query.filter_by(premium_room_id=room.id, user_id=user.id).first() if user else None
    subscription_access = has_subscription_access(user, room.creator_user_id) if user else False
    direct_access_records = active_access_records(user, creator_id=room.creator_user_id) if user else []
    paid_access = any(record.premium_room_id == room.id for record in direct_access_records)

    can_access = room.room_type == "public"
    upgrade_cta = None
    if room.room_type == "subscriber_only":
        can_access = subscription_access or bool(participant)
        upgrade_cta = "Subscribe to join this room"
    elif room.room_type == "paid_entry":
        can_access = paid_access or bool(participant and participant.has_paid_entry)
        upgrade_cta = "Unlock full thread"
    elif room.room_type == "invite_only":
        can_access = bool(participant)
        upgrade_cta = "Request access"
    elif room.room_type == "public":
        can_access = True

    return {
        "can_access": can_access,
        "is_joined": bool(participant),
        "upgrade_cta": upgrade_cta,
        "expires_at": room.expires_at.isoformat() if room.expires_at else None,
        "is_expired": bool(room.expires_at and room.expires_at < now),
    }


def serialize_room(room, user=None):
    if not room:
        return None

    access = room_access_state(user, room) if room else {"can_access": False, "is_joined": False, "upgrade_cta": None, "expires_at": None, "is_expired": False}
    participant_count = room.participants.count() if room else 0
    return {
        "id": room.id,
        "title": room.title,
        "description": room.description or "",
        "room_type": room.room_type,
        "session_kind": room.session_kind,
        "tier_name": room.tier_name,
        "entry_price_cents": room.entry_price_cents,
        "currency": room.currency,
        "participant_cap": room.participant_cap,
        "participant_count": participant_count,
        "scheduled_for": room.scheduled_for.isoformat() if room.scheduled_for else None,
        "expires_at": room.expires_at.isoformat() if room.expires_at else None,
        "video_id": room.video_id,
        "highlighted_reply_id": room.highlighted_reply_id,
        "target_url": room_target_url(room),
        "label": room_label(room),
        **access,
    }


def serialize_subscription_tier(tier, viewer=None):
    active_access = False
    founder_badge = False
    if viewer:
        for record in active_access_records(viewer, creator_id=tier.creator_user_id):
            if record.creator_subscription_id == tier.id:
                active_access = True
                founder_badge = record.founder_badge_granted
                break

    return {
        "id": tier.id,
        "tier_name": tier.tier_name,
        "monthly_price_cents": tier.monthly_price_cents,
        "currency": tier.currency,
        "description": tier.description or "",
        "founder_badges_enabled": tier.founder_badges_enabled,
        "active_access": active_access,
        "founder_badge": founder_badge,
    }


def annotate_videos_with_premium_rooms(videos, viewer=None):
    if not videos:
        return {}
    video_ids = [video.id for video in videos]
    rooms = PremiumVoiceRoom.query.filter(PremiumVoiceRoom.video_id.in_(video_ids), PremiumVoiceRoom.is_active.is_(True)).order_by(PremiumVoiceRoom.created_at.desc()).all()
    room_map = {}
    for room in rooms:
        room_map.setdefault(room.video_id, room)
    for video in videos:
        room = room_map.get(video.id)
        video.premium_room = serialize_room(room, viewer) if room else None
    return room_map


def annotate_hot_thread_cards(cards, room_map, viewer=None):
    for card in cards:
        room = room_map.get(card["video_id"])
        if room:
            card["premium_room"] = serialize_room(room, viewer)
    return cards


def room_for_video(video_id, focused_reply_id=None):
    query = PremiumVoiceRoom.query.filter_by(video_id=video_id, is_active=True)
    if focused_reply_id:
        focused = query.filter_by(highlighted_reply_id=focused_reply_id).order_by(PremiumVoiceRoom.created_at.desc()).first()
        if focused:
            return focused
    return query.order_by(PremiumVoiceRoom.created_at.desc()).first()


def room_replies(room):
    replies = VoiceReply.query.filter_by(video_id=room.video_id).order_by(VoiceReply.created_at.asc()).all()
    if not room.highlighted_reply_id:
        return replies
    descendants = []
    root_id = room.highlighted_reply_id
    child_map = defaultdict(list)
    reply_map = {}
    for reply in replies:
        reply_map[reply.id] = reply
        child_map[reply.parent_reply_id].append(reply)

    def collect(reply_id):
        for child in child_map.get(reply_id, []):
            descendants.append(child)
            collect(child.id)

    root = reply_map.get(root_id)
    if root:
        descendants.append(root)
        collect(root.id)
    return descendants


def preview_reply_tree(serialized_replies, focus_reply_id=None, max_nodes=2):
    if not serialized_replies:
        return []
    if focus_reply_id:
        target = next((reply for reply in serialized_replies if reply["id"] == focus_reply_id), None)
        if target:
            preview = dict(target)
            preview["children"] = preview.get("children", [])[:max_nodes]
            return [preview]
    return serialized_replies[:max_nodes]


def extract_reply_subtree(serialized_replies, focus_reply_id):
    if not focus_reply_id:
        return serialized_replies

    def walk(items):
        for item in items:
            if item["id"] == focus_reply_id:
                return [item]
            children = walk(item.get("children", []))
            if children:
                return children
        return []

    subtree = walk(serialized_replies)
    return subtree or serialized_replies


def apply_supporter_badges(serialized_replies, creator_id):
    for reply in serialized_replies:
        reply["supporter_badge"] = supporter_badge_for_user(reply["user_id"], creator_id)
        if reply.get("children"):
            apply_supporter_badges(reply["children"], creator_id)
    return serialized_replies


def load_my_rooms(user):
    owned = [serialize_room(room, user) for room in user.premium_voice_rooms.order_by(PremiumVoiceRoom.created_at.desc()).all()]
    joined_rows = user.voice_room_participations.order_by(VoiceRoomParticipant.joined_at.desc()).all()
    joined = [serialize_room(row.premium_room, user) for row in joined_rows if row.premium_room]
    return {"owned": owned, "joined": joined}


def creator_earnings_summary(creator):
    tiers = ensure_creator_tiers(creator)
    subscriptions_total = sum(tier.earnings_balance_cents for tier in tiers)
    room_earnings = sum(room.earnings_balance_cents for room in creator.premium_voice_rooms.all())
    tip_rows = creator.received_tip_transactions.all()
    tips_total = sum(row.amount_cents for row in tip_rows)
    rooms = creator.premium_voice_rooms.all()
    room_participant_counts = {room.id: room.participants.count() for room in rooms}
    room_conversion_rate = round(
        sum(room_participant_counts.values()) / max(len(rooms), 1),
        2,
    ) if rooms else 0
    active_accesses = [record for record in creator.subscriber_records.all() if record.access_type == "subscription"]
    now = datetime.utcnow()
    retained = [record for record in active_accesses if not record.expires_at or record.expires_at >= now]
    subscriber_retention = round((len(retained) / len(active_accesses)) * 100, 2) if active_accesses else 0
    avg_tip = round(tips_total / max(len(tip_rows), 1), 2) if tip_rows else 0

    thread_earnings = Counter()
    topic_earnings = Counter()
    supporter_counts = Counter()
    for tip in tip_rows:
        if tip.video_id:
            thread_earnings[tip.video_id] += tip.amount_cents
        if tip.video and tip.video.topic:
            topic_earnings[tip.video.topic] += tip.amount_cents
        if tip.sender:
            supporter_counts[tip.sender.username] += tip.amount_cents

    for room in rooms:
        if room.video_id:
            thread_earnings[room.video_id] += room.earnings_balance_cents
        if room.video and room.video.topic:
            topic_earnings[room.video.topic] += room.earnings_balance_cents

    top_supporters = [
        {"username": username, "amount_cents": amount}
        for username, amount in supporter_counts.most_common(5)
    ]
    top_threads = [
        {"video_id": video_id, "amount_cents": amount}
        for video_id, amount in thread_earnings.most_common(5)
    ]
    best_topics = [
        {"topic": topic, "amount_cents": amount}
        for topic, amount in topic_earnings.most_common(5)
    ]

    return {
        "total_earnings_cents": subscriptions_total + room_earnings + tips_total,
        "subscriptions_total_cents": subscriptions_total,
        "room_earnings_cents": room_earnings,
        "tips_total_cents": tips_total,
        "room_conversion_rate": room_conversion_rate,
        "subscriber_retention": subscriber_retention,
        "avg_tip_per_creator_cents": avg_tip,
        "top_earning_threads": top_threads,
        "best_monetizing_topics": best_topics,
        "top_supporters": top_supporters,
    }


def notify_monetization_event(recipient_id, kind, message, video_id=None, voice_reply_id=None, actor_id=None):
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