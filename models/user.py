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
    text_comments = db.relationship(
        "TextComment",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
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
    creator_subscription_tiers = db.relationship(
        "CreatorSubscription",
        foreign_keys="CreatorSubscription.creator_user_id",
        back_populates="creator",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    subscriber_records = db.relationship(
        "SubscriberAccess",
        foreign_keys="SubscriberAccess.creator_user_id",
        back_populates="creator",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    subscriber_access_records = db.relationship(
        "SubscriberAccess",
        foreign_keys="SubscriberAccess.subscriber_user_id",
        back_populates="subscriber",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    sent_tip_transactions = db.relationship(
        "TipTransaction",
        foreign_keys="TipTransaction.sender_user_id",
        back_populates="sender",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    received_tip_transactions = db.relationship(
        "TipTransaction",
        foreign_keys="TipTransaction.receiver_user_id",
        back_populates="receiver",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    premium_voice_rooms = db.relationship(
        "PremiumVoiceRoom",
        foreign_keys="PremiumVoiceRoom.creator_user_id",
        back_populates="creator",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    voice_room_participations = db.relationship(
        "VoiceRoomParticipant",
        foreign_keys="VoiceRoomParticipant.user_id",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    voice_embeddings = db.relationship(
        "VoiceEmbedding",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    voice_insights = db.relationship(
        "VoiceInsight",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )