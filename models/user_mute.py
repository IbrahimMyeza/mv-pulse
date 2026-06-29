from datetime import datetime

from database import db


class UserMute(db.Model):
    __tablename__ = "user_mute"

    id = db.Column(db.Integer, primary_key=True)
    muter_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    muted_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("muter_id", "muted_id", name="uq_mute_pair"),
    )

    muter = db.relationship("User", foreign_keys=[muter_id])
    muted = db.relationship("User", foreign_keys=[muted_id])
