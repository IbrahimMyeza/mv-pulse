from flask import Blueprint, current_app, redirect, request, session, url_for

from database import db
from ml.debate_detector import controversy_score
from models.video import Video
from models.voice_reply import VoiceReply
from routes.api_responses import auth_required_response, json_error, json_success, wants_json_response
from routes.social_utils import create_notification, current_user, save_video_file, serialize_voice_reply, touch_video_reputation
from services.ai_pipeline import schedule_voice_reply_processing
from services.storage import local_media_path

voice_bp = Blueprint("voice", __name__)
VOICE_FOLDER = "static/voices/replies"


def _analyze_audio(audio_url):
    if not audio_url:
        return "", 0.0
    try:
        from ml.transcriber import transcribe_audio
        from ml.voice_sentiment import analyze_voice_sentiment

        with local_media_path(audio_url) as audio_path:
            if not audio_path:
                return "", 0.0
            transcript = transcribe_audio(audio_path)
            sentiment = analyze_voice_sentiment(transcript)
            return transcript, sentiment
    except Exception:
        current_app.logger.exception("voice.analysis_failed url=%s", audio_url)
        return "", 0.0


def _wants_json_response():
    return wants_json_response()


def _safe_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _reply_response(reply, video, deduplicated=False):
    return json_success(
        reply_id=reply.id,
        video_id=video.id,
        reply=serialize_voice_reply(reply),
        deduplicated=deduplicated,
        redirect_url=url_for("social.video_detail", id=video.id),
        focus_url=f"{url_for('social.video_detail', id=video.id)}?focus_reply_id={reply.id}#reply-{reply.id}",
        voice_replies=video.voice_replies,
        comments=video.comments,
    )


@voice_bp.route("/api/voice/transcribe", methods=["POST"])
def api_voice_transcribe():
    audio = request.files.get("voice") or request.files.get("audio")
    if not audio:
        return json_error("voice file required", status=400)

    audio_url = save_video_file(audio, VOICE_FOLDER)
    transcript, sentiment = _analyze_audio(audio_url)
    debate = controversy_score(sentiment, transcript)

    return json_success(
        audio_url=audio_url,
        transcript=transcript,
        sentiment=sentiment,
        controversy=debate,
    )


@voice_bp.route("/voice/reply", methods=["POST"])
def voice_reply():
    user = current_user()
    if not user:
        if _wants_json_response():
            return auth_required_response(message="Sign in to post voice replies.")
        session["auth_message"] = "Sign in to post voice replies."
        return redirect(url_for("home"))

    video_id = _safe_int(request.form.get("video_id") or request.form.get("id"))
    parent_reply_id = request.form.get("parent_reply_id")
    duration = _safe_float(request.form.get("duration") or 0)
    language_code = (request.form.get("language_code") or "en").strip() or "en"
    audio = request.files.get("voice") or request.files.get("audio")
    client_token = (request.form.get("client_token") or request.headers.get("X-Idempotency-Key") or "").strip()[:128] or None

    if not video_id or not audio:
        return json_error("video_id and audio are required", status=400)

    video = Video.query.get_or_404(video_id)

    if client_token:
        existing_reply = VoiceReply.query.filter_by(
            video_id=video.id,
            user_id=user.id,
            client_token=client_token,
        ).first()
        if existing_reply:
            return _reply_response(existing_reply, video, deduplicated=True)

    audio_url = save_video_file(audio, VOICE_FOLDER)
    transcript, sentiment = _analyze_audio(audio_url)
    debate = controversy_score(sentiment, transcript)

    reply = VoiceReply(
        video_id=video.id,
        user_id=user.id,
        parent_reply_id=int(parent_reply_id) if parent_reply_id else None,
        client_token=client_token,
        audio_url=audio_url,
        duration=duration,
        transcript=transcript,
        language_code=language_code,
        sentiment_score=sentiment,
        controversy_score=debate,
    )
    db.session.add(reply)

    video.voice_replies += 1
    video.comments += 1
    video.debate_score = max(video.debate_score, debate)
    video.emotion_score = max(video.emotion_score, abs(sentiment) or 1.0)
    db.session.commit()
    touch_video_reputation(video, sentiment)
    schedule_voice_reply_processing(reply.id)

    if video.creator_id and video.creator_id != user.id:
        create_notification(
            recipient_id=video.creator_id,
            actor_id=user.id,
            video_id=video.id,
            voice_reply_id=reply.id,
            kind="voice_reply",
            message=f"{user.username} replied to your video with a voice note",
        )

    if reply.parent_reply_id:
        parent = VoiceReply.query.get(reply.parent_reply_id)
        if parent and parent.user_id != user.id:
            create_notification(
                recipient_id=parent.user_id,
                actor_id=user.id,
                video_id=video.id,
                voice_reply_id=reply.id,
                kind="thread_reply",
                message=f"{user.username} replied to your voice note",
            )

    if _wants_json_response():
        return _reply_response(reply, video)

    return redirect(url_for("social.video_detail", id=video.id))


@voice_bp.route("/upload_voice", methods=["POST"])
def upload_voice():
    return api_voice_transcribe()
