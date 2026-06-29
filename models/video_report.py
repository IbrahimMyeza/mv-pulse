from datetime import datetime

from database import db


class VideoReport(db.Model):
    __tablename__ = "video_report"

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = db.Column(db.Integer, db.ForeignKey("video.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = db.Column(db.String(50), nullable=False, default="other")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("reporter_id", "video_id", name="uq_report_pair"),
    )

    reporter = db.relationship("User", foreign_keys=[reporter_id])
    video = db.relationship("Video", foreign_keys=[video_id])
