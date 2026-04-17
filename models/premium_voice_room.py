from datetime import datetime

from database import db


class PremiumVoiceRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"), nullable=True, index=True)
    highlighted_reply_id = db.Column(db.Integer, db.ForeignKey("voice_reply.id"), nullable=True, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    room_type = db.Column(db.String(40), nullable=False, default="public")
    session_kind = db.Column(db.String(40), nullable=False, default="debate")
    tier_name = db.Column(db.String(80), nullable=True)
    entry_price_cents = db.Column(db.Integer, nullable=False, default=0)
    currency = db.Column(db.String(8), nullable=False, default="ZAR")
    founder_badges_enabled = db.Column(db.Boolean, nullable=False, default=False)
    scheduled_for = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    participant_cap = db.Column(db.Integer, nullable=False, default=100)
    earnings_balance_cents = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    creator = db.relationship("User", foreign_keys=[creator_user_id], back_populates="premium_voice_rooms")
    video = db.relationship("Video")
    highlighted_reply = db.relationship("VoiceReply", foreign_keys=[highlighted_reply_id])
    participants = db.relationship(
        "VoiceRoomParticipant",
        back_populates="premium_room",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    tip_transactions = db.relationship(
        "TipTransaction",
        back_populates="premium_room",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    subscriber_access_records = db.relationship(
        "SubscriberAccess",
        back_populates="premium_room",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )