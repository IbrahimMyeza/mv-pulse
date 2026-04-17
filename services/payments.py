from datetime import datetime, timedelta

from database import db
from models.creator_subscription import CreatorSubscription
from models.subscriber_access import SubscriberAccess
from models.tip_transaction import TipTransaction

DEFAULT_CURRENCY = "ZAR"


def activate_subscription_access(subscriber, subscription_tier):
    access = SubscriberAccess.query.filter_by(
        creator_user_id=subscription_tier.creator_user_id,
        subscriber_user_id=subscriber.id,
        creator_subscription_id=subscription_tier.id,
        access_type="subscription",
    ).first()

    founder_badge_granted = False
    if not access:
        founder_badge_granted = (
            subscription_tier.founder_badges_enabled
            and subscription_tier.subscriber_access_records.count() < subscription_tier.founder_badge_limit
        )
        access = SubscriberAccess(
            creator_user_id=subscription_tier.creator_user_id,
            subscriber_user_id=subscriber.id,
            creator_subscription_id=subscription_tier.id,
            access_type="subscription",
            tier_name=subscription_tier.tier_name,
            founder_badge_granted=founder_badge_granted,
        )
        db.session.add(access)

    access.expires_at = datetime.utcnow() + timedelta(days=30)
    access.tier_name = subscription_tier.tier_name
    subscription_tier.earnings_balance_cents += subscription_tier.monthly_price_cents
    db.session.commit()
    return access


def grant_paid_room_access(user, room, amount_cents):
    access = SubscriberAccess.query.filter_by(
        creator_user_id=room.creator_user_id,
        subscriber_user_id=user.id,
        premium_room_id=room.id,
        access_type="paid_room",
    ).first()

    if not access:
        access = SubscriberAccess(
            creator_user_id=room.creator_user_id,
            subscriber_user_id=user.id,
            premium_room_id=room.id,
            video_id=room.video_id,
            access_type="paid_room",
            tier_name=room.tier_name,
        )
        db.session.add(access)

    access.expires_at = room.expires_at
    room.earnings_balance_cents += amount_cents
    db.session.commit()
    return access


def grant_paid_thread_unlock(user, room, amount_cents):
    access = SubscriberAccess.query.filter_by(
        creator_user_id=room.creator_user_id,
        subscriber_user_id=user.id,
        premium_room_id=room.id,
        access_type="thread_unlock",
    ).first()

    if not access:
        access = SubscriberAccess(
            creator_user_id=room.creator_user_id,
            subscriber_user_id=user.id,
            premium_room_id=room.id,
            video_id=room.video_id,
            access_type="thread_unlock",
            tier_name=room.tier_name,
        )
        db.session.add(access)

    access.expires_at = room.expires_at
    room.earnings_balance_cents += amount_cents
    db.session.commit()
    return access


def record_tip_transaction(sender, receiver, amount_cents, currency=DEFAULT_CURRENCY, video=None, voice_reply=None, premium_room=None):
    transaction = TipTransaction(
        sender_user_id=sender.id,
        receiver_user_id=receiver.id,
        amount_cents=amount_cents,
        currency=currency,
        content_type="premium_room" if premium_room else "voice_reply" if voice_reply else "video",
        video_id=video.id if video else None,
        voice_reply_id=voice_reply.id if voice_reply else None,
        premium_room_id=premium_room.id if premium_room else None,
    )
    db.session.add(transaction)
    if premium_room:
        premium_room.earnings_balance_cents += amount_cents
    db.session.commit()
    return transaction