from datetime import datetime

from database import db


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    video_path = db.Column(db.String(400), nullable=False)
    thumbnail_url = db.Column(db.String(400), nullable=True)
    language_code = db.Column(db.String(10), nullable=False, default="en")
    alternate_language_code = db.Column(db.String(10), nullable=False, default="zu")
    topic = db.Column(db.String(100), nullable=False, default="general")
    region = db.Column(db.String(100), nullable=False, default="Durban")
    category = db.Column(db.String(100), nullable=False, default="general")
    transcript_summary = db.Column(db.Text, nullable=True)
    likes = db.Column(db.Integer, nullable=False, default=0)
    views = db.Column(db.Integer, nullable=False, default=0)
    comments = db.Column(db.Integer, nullable=False, default=0)
    shares_count = db.Column(db.Integer, nullable=False, default=0)
    watch_time = db.Column(db.Integer, nullable=False, default=0)
    creator_score = db.Column(db.Float, nullable=False, default=1.0)
    report_count = db.Column(db.Integer, nullable=False, default=0)
    voice_replies = db.Column(db.Integer, nullable=False, default=0)
    emotion_score = db.Column(db.Float, nullable=False, default=1.0)
    debate_score = db.Column(db.Float, nullable=False, default=0.0)
    community_score = db.Column(db.Float, nullable=False, default=1.0)
    is_public = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    creator = db.relationship("User", back_populates="videos")
    replies = db.relationship(
        "VoiceReply",
        back_populates="video",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    like_records = db.relationship(
        "Like",
        back_populates="video",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    save_records = db.relationship(
        "Save",
        back_populates="video",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    thread_summaries = db.relationship(
        "ThreadSummary",
        back_populates="video",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )