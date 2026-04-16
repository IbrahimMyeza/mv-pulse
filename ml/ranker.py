from datetime import datetime
from ml.debate_detector import controversy_score
from ml.reputation import get_creator_score
from ml.spam_detector import spam_penalty

def emotion_boost(sentiment_score):
    return abs(sentiment_score) * 20


def calculate_virality(reel):
    """Calculate predicted virality score"""
    return (
        reel.likes * 3
        + reel.views
        + reel.comments * 2
        + reel.watch_time * 1.5
        + getattr(reel, "debate_score", 0) * 50
    )


def score_reel(reel):
    """Score a reel with virality prediction boost"""
    base_score = (
        reel.likes * 2
        + reel.views
        + reel.comments * 3
        + reel.watch_time * 1.5
        + getattr(reel, "debate_score", 0) * 40
        + getattr(reel, "community_score", 1.0) * 30
        + getattr(reel, "creator_score", 1.0) * 50
    )

    predicted_virality = calculate_virality(reel)

    if predicted_virality > 2000:
        base_score += 500

    return base_score


def rank_reels(reels, preferred_topic=None, preferred_region=None):
    scored = []

    for reel in reels:
        age_hours = 1

        if hasattr(reel, "created_at") and reel.created_at:
            age = datetime.utcnow() - reel.created_at
            age_hours = max(age.total_seconds() / 3600, 1)

        virality = score_reel(reel)
        freshness_boost = 100 / age_hours
        creator_boost = getattr(reel, "creator_score", 1.0) * 50
        trust_penalty = getattr(reel, "report_count", 0) * 25
        voice_boost = getattr(reel, "voice_replies", 0) * 10
        emotion_multiplier = getattr(reel, "emotion_score", 1.0) * 40
        debate_boost = getattr(reel, "debate_score", 0.0) * 60
        community_boost = getattr(reel, "community_score", 1.0) * 35

        topic_match = 50 if preferred_topic and getattr(reel, "topic", "general") == preferred_topic else 0
        region_match = 40 if preferred_region and getattr(reel, "region", "Durban") == preferred_region else 0

        score = (
            virality
            + freshness_boost
            + creator_boost
            - trust_penalty
            + voice_boost
            + emotion_multiplier
            + debate_boost
            + community_boost
            + topic_match
            + region_match
        )

        scored.append((score, reel))

    scored.sort(reverse=True, key=lambda x: x[0])

    return [reel for score, reel in scored]


def rank_reels_for_user(reels, top_categories, preferred_topic=None, preferred_region=None):
    def score(reel):
        age_hours = 1

        if hasattr(reel, "created_at") and reel.created_at:
            age = datetime.utcnow() - reel.created_at
            age_hours = max(age.total_seconds() / 3600, 1)

        base = score_reel(reel)

        if getattr(reel, "category", "general") in top_categories:
            base += 50

        voice_score = getattr(reel, "voice_sentiment", 0)
        base += emotion_boost(voice_score)

        debate = controversy_score(
            getattr(reel, "voice_sentiment", 0),
            getattr(reel, "transcript", "")
        )
        base += debate

        creator_score = get_creator_score(getattr(reel, "creator_id", 0))
        base += creator_score * 0.2

        base -= spam_penalty(reel)

        freshness_boost = 100 / age_hours
        creator_boost = getattr(reel, "creator_score", 1.0) * 50
        trust_penalty = getattr(reel, "report_count", 0) * 25
        voice_boost = getattr(reel, "voice_replies", 0) * 10
        emotion_multiplier = getattr(reel, "emotion_score", 1.0) * 40
        debate_boost = getattr(reel, "debate_score", 0.0) * 60
        community_boost = getattr(reel, "community_score", 1.0) * 35

        topic_match = 50 if preferred_topic and getattr(reel, "topic", "general") == preferred_topic else 0
        region_match = 40 if preferred_region and getattr(reel, "region", "Durban") == preferred_region else 0

        return (
            base
            + freshness_boost
            + creator_boost
            - trust_penalty
            + voice_boost
            + emotion_multiplier
            + debate_boost
            + community_boost
            + topic_match
            + region_match
        )

    return sorted(reels, key=score, reverse=True)