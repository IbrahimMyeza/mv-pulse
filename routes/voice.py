from flask import Blueprint, request, jsonify
import os

from ml.transcriber import transcribe_audio
from ml.voice_sentiment import analyze_voice_sentiment

voice_bp = Blueprint("voice", __name__)
VOICE_FOLDER = "static/voices"


@voice_bp.route("/upload_voice", methods=["POST"])
def upload_voice():
    voice = request.files.get("voice")

    if not voice:
        return jsonify({"error": "voice file required"}), 400

    os.makedirs(VOICE_FOLDER, exist_ok=True)

    file_path = os.path.join(VOICE_FOLDER, voice.filename)
    voice.save(file_path)

    transcript = transcribe_audio(file_path)
    sentiment = analyze_voice_sentiment(transcript)

    return jsonify({
        "message": "voice uploaded",
        "transcript": transcript,
        "sentiment": sentiment
    })