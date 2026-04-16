from flask import Blueprint, jsonify
from models.reel import Reel

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/analytics")
def analytics():
    reels = Reel.query.all()

    total_reels = len(reels)
    total_views = sum(r.views for r in reels) if reels else 0
    total_likes = sum(r.likes for r in reels) if reels else 0

    avg_trust = (
        sum(getattr(r, "creator_score", 1.0) for r in reels) / total_reels
        if total_reels else 0
    )

    avg_debate = (
        sum(getattr(r, "debate_score", 0.0) for r in reels) / total_reels
        if total_reels else 0
    )

    topics = {}
    for reel in reels:
        topic = getattr(reel, "topic", "general")
        topics[topic] = topics.get(topic, 0) + 1

    top_topic = max(topics, key=topics.get) if topics else "none"

    return jsonify({
        "total_reels": total_reels,
        "total_views": total_views,
        "total_likes": total_likes,
        "avg_trust": round(avg_trust, 2),
        "avg_debate": round(avg_debate, 2),
        "top_topic": top_topic
    })