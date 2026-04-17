from datetime import datetime

from database import db


class VoiceInsight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    voice_reply_id = db.Column(db.Integer, db.ForeignKey("voice_reply.id"), nullable=False, index=True, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    topic_label = db.Column(db.String(80), nullable=False, default="general")
    topic_confidence = db.Column(db.Float, nullable=False, default=0.0)
    sentiment_score = db.Column(db.Float, nullable=False, default=0.0)
    toxicity_score = db.Column(db.Float, nullable=False, default=0.0)
    controversy_score = db.Column(db.Float, nullable=False, default=0.0)
    tone_label = db.Column(db.String(80), nullable=False, default="balanced")
    energy_score = db.Column(db.Float, nullable=False, default=0.0)
    replay_signal = db.Column(db.Float, nullable=False, default=0.0)
    intelligence_score = db.Column(db.Float, nullable=False, default=0.0)
    moderation_state = db.Column(db.String(40), nullable=False, default="clear")
    processing_state = db.Column(db.String(40), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    voice_reply = db.relationship("VoiceReply", back_populates="insight_record")
    user = db.relationship("User", back_populates="voice_insights")
