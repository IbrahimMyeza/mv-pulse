from datetime import datetime

from database import db


class TipTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    receiver_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    amount_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(8), nullable=False, default="ZAR")
    content_type = db.Column(db.String(40), nullable=False, default="video")
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"), nullable=True, index=True)
    voice_reply_id = db.Column(db.Integer, db.ForeignKey("voice_reply.id"), nullable=True, index=True)
    premium_room_id = db.Column(db.Integer, db.ForeignKey("premium_voice_room.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    sender = db.relationship("User", foreign_keys=[sender_user_id], back_populates="sent_tip_transactions")
    receiver = db.relationship("User", foreign_keys=[receiver_user_id], back_populates="received_tip_transactions")
    video = db.relationship("Video")
    voice_reply = db.relationship("VoiceReply")
    premium_room = db.relationship("PremiumVoiceRoom", back_populates="tip_transactions")