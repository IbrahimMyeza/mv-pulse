from datetime import datetime

from database import db


class UserSocialProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(120), nullable=False)
    headline = db.Column(db.String(160), nullable=False, default="Voice-first creator")
    bio = db.Column(db.Text, nullable=True)
    avatar_url = db.Column(db.String(400), nullable=True)
    region = db.Column(db.String(100), nullable=False, default="Durban")
    primary_language_code = db.Column(db.String(10), nullable=False, default="en")
    secondary_language_code = db.Column(db.String(10), nullable=False, default="zu")
    voice_style = db.Column(db.String(120), nullable=False, default="community")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = db.relationship("User", back_populates="social_profile")