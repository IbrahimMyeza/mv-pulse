from database import db

class Reel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    video_path = db.Column(db.String(300), nullable=False)

    likes = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    watch_time = db.Column(db.Integer, default=0)
    comments = db.Column(db.Integer, default=0)
    category = db.Column(db.String(100), default="general")
    creator_score = db.Column(db.Float, default=1.0)
    report_count = db.Column(db.Integer, default=0)
    voice_replies = db.Column(db.Integer, default=0)
    emotion_score = db.Column(db.Float, default=1.0)
    debate_score = db.Column(db.Float, default=0.0)
    topic = db.Column(db.String(100), default="general")
    community_score = db.Column(db.Float, default=1.0)
    region = db.Column(db.String(100), default="Durban")
    agree_count = db.Column(db.Integer, default=0)
    disagree_count = db.Column(db.Integer, default=0)