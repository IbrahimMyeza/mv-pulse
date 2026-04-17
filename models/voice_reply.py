from datetime import datetime

from database import db


class VoiceReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    parent_reply_id = db.Column(db.Integer, db.ForeignKey("voice_reply.id"), nullable=True, index=True)
    client_token = db.Column(db.String(128), nullable=True, index=True)
    audio_url = db.Column(db.String(400), nullable=False)
    duration = db.Column(db.Float, nullable=False, default=0)
    transcript = db.Column(db.Text, nullable=True)
    language_code = db.Column(db.String(10), nullable=False, default="en")
    likes_count = db.Column(db.Integer, nullable=False, default=0)
    sentiment_score = db.Column(db.Float, nullable=False, default=0.0)
    controversy_score = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    video = db.relationship("Video", back_populates="replies")
    creator = db.relationship("User", back_populates="voice_replies")
    parent_reply = db.relationship("VoiceReply", remote_side=[id], backref=db.backref("child_replies", lazy="joined"))
    like_records = db.relationship(
        "Like",
        back_populates="voice_reply",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    save_records = db.relationship(
        "Save",
        back_populates="voice_reply",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    embedding_record = db.relationship(
        "VoiceEmbedding",
        back_populates="voice_reply",
        uselist=False,
        cascade="all, delete-orphan",
    )
    insight_record = db.relationship(
        "VoiceInsight",
        back_populates="voice_reply",
        uselist=False,
        cascade="all, delete-orphan",
    )