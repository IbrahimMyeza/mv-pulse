from datetime import datetime

from database import db


class Save(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"), nullable=True, index=True)
    reel_id = db.Column(db.Integer, db.ForeignKey("reel.id"), nullable=True, index=True)
    voice_reply_id = db.Column(db.Integer, db.ForeignKey("voice_reply.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint(
            "video_id IS NOT NULL OR reel_id IS NOT NULL OR voice_reply_id IS NOT NULL",
            name="ck_save_has_target",
        ),
        db.UniqueConstraint("user_id", "video_id", name="uq_save_user_video"),
        db.UniqueConstraint("user_id", "reel_id", name="uq_save_user_reel"),
        db.UniqueConstraint("user_id", "voice_reply_id", name="uq_save_user_voice_reply"),
    )

    user = db.relationship("User", back_populates="saves")
    video = db.relationship("Video", back_populates="save_records")
    reel = db.relationship("Reel", back_populates="save_records")
    voice_reply = db.relationship("VoiceReply", back_populates="save_records")