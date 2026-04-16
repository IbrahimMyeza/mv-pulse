from datetime import datetime

from database import db


class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    followed_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("follower_id", "followed_id", name="uq_follow_pair"),
    )

    follower = db.relationship("User", foreign_keys=[follower_id], back_populates="following")
    followed = db.relationship("User", foreign_keys=[followed_id], back_populates="followers")