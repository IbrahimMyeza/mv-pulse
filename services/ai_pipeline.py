import hashlib
import json
import math
import os
import threading
from collections import Counter
from services.storage import local_media_path

from flask import current_app

from database import db
from models.video import Video
from models.voice_embedding import VoiceEmbedding
from models.voice_insight import VoiceInsight
from models.voice_reply import VoiceReply
from services.moderation_ai import moderation_assessment
from services.thread_intelligence import refresh_thread_summary
from services.thread_heat import REPLY_LISTEN_COUNTS

PIPELINE_LOCKS = set()
EMBEDDING_DIM = 24
EMBEDDING_MODEL = "mv-hash-v1"
TOPIC_KEYWORDS = {
    "politics": ["government", "president", "policy", "minister", "vote", "parliament", "politics"],
    "football": ["football", "goal", "match", "league", "coach", "stadium"],
    "religion": ["church", "faith", "religion", "prayer", "god", "mosque"],
    "campus": ["campus", "student", "lecture", "university", "exam"],
    "music": ["music", "song", "album", "artist", "beat", "sound"],
    "relationships": ["dating", "love", "relationship", "partner", "marriage"],
    "business": ["money", "business", "market", "startup", "sales", "invest"],
}


def _tokenize(text):
    cleaned = [token.strip(".,!?;:'\"()[]{}") for token in (text or "").lower().split()]
    return [token for token in cleaned if token]


def _embedding_for_text(text):
    vector = [0.0] * EMBEDDING_DIM
    tokens = _tokenize(text)
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        bucket = int(digest[:2], 16) % EMBEDDING_DIM
        vector[bucket] += (int(digest[2:4], 16) / 255.0) + 0.1
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 4) for value in vector]


def _topic_for_reply(text, video=None):
    tokens = set(_tokenize(text))
    best_label = (video.topic if video and video.topic else "general") or "general"
    best_score = 0
    video_topic = ((video.topic if video else "") or "").lower().strip()
    if video_topic and video_topic in tokens:
        best_score = 1
        best_label = video_topic
    for label, keywords in TOPIC_KEYWORDS.items():
        score = len(tokens.intersection(keywords))
        if score > best_score or (score == best_score and label == video_topic and score > 0):
            best_label = label
            best_score = score
    confidence = round(min(1.0, 0.2 + (best_score * 0.2)), 2) if best_score else 0.25
    return best_label, confidence


def _tone_label(text, sentiment_score, toxicity_score):
    lower = (text or "").lower()
    if any(marker in lower for marker in ["haha", "lol", "joke", "funny"]):
        return "humorous"
    if toxicity_score >= 0.45:
        return "aggressive"
    if any(marker in lower for marker in ["because", "therefore", "evidence", "reason", "data"]):
        return "analytical"
    if sentiment_score <= -0.2:
        return "heated"
    if sentiment_score >= 0.3:
        return "optimistic"
    return "balanced"


def _energy_score(text, reply):
    content = text or ""
    if not content:
        return 0.0
    exclamations = min(content.count("!"), 5) * 0.08
    uppercase_ratio = min(sum(1 for token in content.split() if token.isupper() and len(token) > 3), 4) * 0.08
    duration_bonus = min((reply.duration or 0) / 20.0, 0.35)
    length_bonus = min(len(content.split()) / 60.0, 0.25)
    return round(min(exclamations + uppercase_ratio + duration_bonus + length_bonus, 1.0), 2)


def _replay_signal(reply):
    listens = REPLY_LISTEN_COUNTS.get(reply.id, 0)
    likes = reply.likes_count or 0
    return round(min((listens * 0.12) + (likes * 0.08), 1.0), 2)


def _intelligence_score(sentiment_score, toxicity_score, controversy_score, energy_score, replay_signal, topic_confidence):
    raw = (abs(sentiment_score) * 0.2) + (max(controversy_score, 0) * 0.25) + (energy_score * 0.2) + (replay_signal * 0.2) + (topic_confidence * 0.15)
    penalty = 0.25 if toxicity_score >= 0.72 else 0.12 if toxicity_score >= 0.45 else 0.0
    return round(max(raw - penalty, 0.0), 2)


def _ensure_insight(reply):
    insight = VoiceInsight.query.filter_by(voice_reply_id=reply.id).first()
    if not insight:
        insight = VoiceInsight(voice_reply_id=reply.id, user_id=reply.user_id)
        db.session.add(insight)
        db.session.commit()
    return insight


def process_voice_reply(reply_id):
    reply = VoiceReply.query.get(reply_id)
    if not reply:
        return None

    insight = _ensure_insight(reply)
    insight.processing_state = "pending"
    db.session.commit()

    try:
        video = Video.query.get(reply.video_id)
        transcript = (reply.transcript or "").strip()
        if not transcript and reply.audio_url:
            from ml.transcriber import transcribe_audio

            with local_media_path(reply.audio_url) as audio_path:
                transcript = transcribe_audio(audio_path) if audio_path else ""
            reply.transcript = transcript

        if transcript:
            try:
                from ml.voice_sentiment import analyze_voice_sentiment

                sentiment_score = round(float(analyze_voice_sentiment(transcript) or 0.0), 2)
            except Exception:
                sentiment_score = round(reply.sentiment_score or 0.0, 2)
        else:
            sentiment_score = round(reply.sentiment_score or 0.0, 2)

        moderation = moderation_assessment(transcript)
        topic_label, topic_confidence = _topic_for_reply(transcript, video=video)
        tone_label = _tone_label(transcript, sentiment_score, moderation["toxicity_score"])
        energy_score = _energy_score(transcript, reply)
        replay_signal = _replay_signal(reply)
        controversy_value = round(max(reply.controversy_score or 0.0, abs(sentiment_score) * 0.4), 2)
        intelligence_score = _intelligence_score(
            sentiment_score,
            moderation["toxicity_score"],
            controversy_value,
            energy_score,
            replay_signal,
            topic_confidence,
        )

        embedding = VoiceEmbedding.query.filter_by(voice_reply_id=reply.id).first()
        if not embedding:
            embedding = VoiceEmbedding(voice_reply_id=reply.id, user_id=reply.user_id)
            db.session.add(embedding)

        vector = _embedding_for_text(transcript)
        embedding.embedding_model = EMBEDDING_MODEL
        embedding.embedding_vector_json = json.dumps(vector)
        embedding.embedding_dim = len(vector)

        insight.topic_label = topic_label
        insight.topic_confidence = topic_confidence
        insight.sentiment_score = sentiment_score
        insight.toxicity_score = moderation["toxicity_score"]
        insight.controversy_score = controversy_value
        insight.tone_label = tone_label
        insight.energy_score = energy_score
        insight.replay_signal = replay_signal
        insight.intelligence_score = intelligence_score
        insight.moderation_state = moderation["moderation_state"]
        insight.processing_state = "partial" if not transcript else "complete"

        db.session.commit()
        refresh_thread_summary(reply.video_id)
        return insight
    except Exception:
        insight.processing_state = "failed"
        db.session.commit()
        return insight


def schedule_voice_reply_processing(reply_id):
    reply = VoiceReply.query.get(reply_id)
    if not reply:
        return False
    _ensure_insight(reply)
    app = current_app._get_current_object() if current_app else None
    if not app:
        return False
    if app.config.get("TESTING") or os.getenv("MV_M7_DISABLE_ASYNC") == "1":
        process_voice_reply(reply_id)
        return True
    if reply_id in PIPELINE_LOCKS:
        return False

    def runner():
        PIPELINE_LOCKS.add(reply_id)
        try:
            with app.app_context():
                process_voice_reply(reply_id)
                db.session.remove()
        finally:
            PIPELINE_LOCKS.discard(reply_id)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return True


def ensure_processed_for_video(video_id):
    replies = VoiceReply.query.filter_by(video_id=video_id).all()
    reply_ids = [reply.id for reply in replies]
    existing = {
        row.voice_reply_id: row for row in VoiceInsight.query.filter(VoiceInsight.voice_reply_id.in_(reply_ids)).all()
    } if reply_ids else {}
    for reply in replies:
        row = existing.get(reply.id)
        if row is None or row.processing_state in {"pending", "failed"}:
            process_voice_reply(reply.id)


def intelligence_snapshot_for_video(video_id):
    rows = (
        VoiceInsight.query.join(VoiceReply, VoiceReply.id == VoiceInsight.voice_reply_id)
        .filter(VoiceReply.video_id == video_id)
        .all()
    )
    topic_counts = Counter(row.topic_label for row in rows if row.topic_label)
    return {
        "avg_intelligence_score": round(sum(row.intelligence_score for row in rows) / len(rows), 2) if rows else 0.0,
        "avg_toxicity_score": round(sum(row.toxicity_score for row in rows) / len(rows), 2) if rows else 0.0,
        "dominant_topics": [label for label, _ in topic_counts.most_common(3)],
    }