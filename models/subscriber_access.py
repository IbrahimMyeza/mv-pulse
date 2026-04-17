from datetime import datetime

from database import db


class SubscriberAccess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    subscriber_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    creator_subscription_id = db.Column(db.Integer, db.ForeignKey("creator_subscription.id"), nullable=True, index=True)
    premium_room_id = db.Column(db.Integer, db.ForeignKey("premium_voice_room.id"), nullable=True, index=True)
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"), nullable=True, index=True)
    access_type = db.Column(db.String(40), nullable=False, default="subscription")
    tier_name = db.Column(db.String(80), nullable=True)
    founder_badge_granted = db.Column(db.Boolean, nullable=False, default=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    creator = db.relationship("User", foreign_keys=[creator_user_id], back_populates="subscriber_records")
    subscriber = db.relationship("User", foreign_keys=[subscriber_user_id], back_populates="subscriber_access_records")
    subscription_tier = db.relationship("CreatorSubscription", back_populates="subscriber_access_records")
    premium_room = db.relationship("PremiumVoiceRoom", back_populates="subscriber_access_records")
    video = db.relationship("Video")