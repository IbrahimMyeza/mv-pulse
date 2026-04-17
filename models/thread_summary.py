from datetime import datetime

from database import db


class ThreadSummary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"), nullable=False, index=True)
    root_reply_id = db.Column(db.Integer, db.ForeignKey("voice_reply.id"), nullable=True, index=True)
    summary_text = db.Column(db.Text, nullable=False, default="")
    cluster_label = db.Column(db.String(80), nullable=False, default="general")
    controversy_score = db.Column(db.Float, nullable=False, default=0.0)
    reply_velocity = db.Column(db.Float, nullable=False, default=0.0)
    participant_count = db.Column(db.Integer, nullable=False, default=0)
    last_computed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("video_id", "root_reply_id", name="uq_thread_summary_scope"),
    )

    video = db.relationship("Video", back_populates="thread_summaries")
    root_reply = db.relationship("VoiceReply", foreign_keys=[root_reply_id])
