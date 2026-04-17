import json
from datetime import datetime

from database import db


class VoiceEmbedding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    voice_reply_id = db.Column(db.Integer, db.ForeignKey("voice_reply.id"), nullable=False, index=True, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    embedding_model = db.Column(db.String(80), nullable=False, default="mv-hash-v1")
    embedding_vector_json = db.Column(db.Text, nullable=False, default="[]")
    embedding_dim = db.Column(db.Integer, nullable=False, default=24)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    voice_reply = db.relationship("VoiceReply", back_populates="embedding_record")
    user = db.relationship("User", back_populates="voice_embeddings")

    @property
    def embedding_vector(self):
        try:
            return json.loads(self.embedding_vector_json or "[]")
        except json.JSONDecodeError:
            return []
