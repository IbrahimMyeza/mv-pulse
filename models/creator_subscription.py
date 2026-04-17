from datetime import datetime

from database import db


class CreatorSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    tier_name = db.Column(db.String(80), nullable=False)
    monthly_price_cents = db.Column(db.Integer, nullable=False, default=0)
    currency = db.Column(db.String(8), nullable=False, default="ZAR")
    description = db.Column(db.String(255), nullable=True)
    founder_badges_enabled = db.Column(db.Boolean, nullable=False, default=False)
    founder_badge_limit = db.Column(db.Integer, nullable=False, default=25)
    earnings_balance_cents = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("creator_user_id", "tier_name", name="uq_creator_subscription_tier"),
    )

    creator = db.relationship("User", foreign_keys=[creator_user_id], back_populates="creator_subscription_tiers")
    subscriber_access_records = db.relationship(
        "SubscriberAccess",
        back_populates="subscription_tier",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )