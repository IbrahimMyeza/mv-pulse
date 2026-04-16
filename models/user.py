from database import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    social_profile = db.relationship(
        "UserSocialProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    videos = db.relationship("Video", back_populates="creator", lazy="dynamic")
    voice_replies = db.relationship("VoiceReply", back_populates="creator", lazy="dynamic")
    likes = db.relationship(
        "Like",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    saves = db.relationship(
        "Save",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    following = db.relationship(
        "Follow",
        foreign_keys="Follow.follower_id",
        back_populates="follower",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    followers = db.relationship(
        "Follow",
        foreign_keys="Follow.followed_id",
        back_populates="followed",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    notifications = db.relationship(
        "Notification",
        foreign_keys="Notification.recipient_user_id",
        back_populates="recipient",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )