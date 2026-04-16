from flask import Blueprint, jsonify, redirect, request, session, url_for

from database import db
from ml.debate_detector import controversy_score
from ml.transcriber import transcribe_audio
from ml.voice_sentiment import analyze_voice_sentiment
from models.video import Video
from models.voice_reply import VoiceReply
from routes.social_utils import create_notification, current_user, save_video_file, touch_video_reputation

voice_bp = Blueprint("voice", __name__)
VOICE_FOLDER = "static/voices/replies"


@voice_bp.route("/api/voice/transcribe", methods=["POST"])
def api_voice_transcribe():
    audio = request.files.get("voice") or request.files.get("audio")
    if not audio:
        return jsonify({"error": "voice file required"}), 400

    audio_url = save_video_file(audio, VOICE_FOLDER)
    audio_path = audio_url.lstrip("/")
    transcript = transcribe_audio(audio_path)
    sentiment = analyze_voice_sentiment(transcript)
    debate = controversy_score(sentiment, transcript)

    return jsonify({
        "audio_url": audio_url,
        "transcript": transcript,
        "sentiment": sentiment,
        "controversy": debate,
    })


@voice_bp.route("/voice/reply", methods=["POST"])
def voice_reply():
    user = current_user()
    if not user:
        session["auth_message"] = "Sign in to post voice replies."
        return redirect(url_for("home"))

    video_id = request.form.get("video_id") or request.form.get("id")
    parent_reply_id = request.form.get("parent_reply_id")
    duration = float(request.form.get("duration") or 0)
    language_code = (request.form.get("language_code") or "en").strip() or "en"
    audio = request.files.get("voice") or request.files.get("audio")

    if not video_id or not audio:
        return jsonify({"error": "video_id and audio are required"}), 400

    video = Video.query.get_or_404(int(video_id))
    audio_url = save_video_file(audio, VOICE_FOLDER)
    audio_path = audio_url.lstrip("/")
    transcript = transcribe_audio(audio_path)
    sentiment = analyze_voice_sentiment(transcript)
    debate = controversy_score(sentiment, transcript)

    reply = VoiceReply(
        video_id=video.id,
        user_id=user.id,
        parent_reply_id=int(parent_reply_id) if parent_reply_id else None,
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

    return redirect(url_for("social.video_detail", id=video.id))


@voice_bp.route("/upload_voice", methods=["POST"])
def upload_voice():
    return api_voice_transcribe()
