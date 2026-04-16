from datetime import datetime

from database import db


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"), nullable=True, index=True)
    voice_reply_id = db.Column(db.Integer, db.ForeignKey("voice_reply.id"), nullable=True, index=True)
    kind = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    recipient = db.relationship("User", foreign_keys=[recipient_user_id], back_populates="notifications")
    actor = db.relationship("User", foreign_keys=[actor_user_id])
    video = db.relationship("Video")
    voice_reply = db.relationship("VoiceReply")