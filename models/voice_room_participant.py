from datetime import datetime

from database import db


class VoiceRoomParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    premium_room_id = db.Column(db.Integer, db.ForeignKey("premium_voice_room.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    role = db.Column(db.String(40), nullable=False, default="listener")
    has_paid_entry = db.Column(db.Boolean, nullable=False, default=False)
    joined_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("premium_room_id", "user_id", name="uq_voice_room_user"),
    )

    premium_room = db.relationship("PremiumVoiceRoom", back_populates="participants")
    user = db.relationship("User", back_populates="voice_room_participations")