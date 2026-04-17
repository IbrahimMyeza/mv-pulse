from datetime import datetime

from database import db


class TextComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"), nullable=False, index=True)
    content = db.Column(db.String(280), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="text_comments")
    video = db.relationship("Video", back_populates="text_comments")