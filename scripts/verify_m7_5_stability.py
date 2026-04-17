import io
import os
import sys
import warnings
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERIFY_DB = ROOT / "instance" / f"m7_5_stability_{os.getpid()}.db"
VERIFY_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{VERIFY_DB.as_posix()}"
os.environ["MV_M7_DISABLE_ASYNC"] = "1"
warnings.filterwarnings("ignore", category=DeprecationWarning, message=r"datetime\.datetime\.utcnow\(\) is deprecated")

stub_transcriber = ModuleType("ml.transcriber")
stub_transcriber.transcribe_audio = lambda path: "This is a stable duplicate-safe voice reply for verification"
sys.modules["ml.transcriber"] = stub_transcriber

stub_sentiment = ModuleType("ml.voice_sentiment")
stub_sentiment.analyze_voice_sentiment = lambda text: 0.22
sys.modules["ml.voice_sentiment"] = stub_sentiment

stub_debate = ModuleType("ml.debate_detector")
stub_debate.controversy_score = lambda sentiment, transcript: 0.35
sys.modules["ml.debate_detector"] = stub_debate

stub_ranker = ModuleType("ml.ranker")
stub_ranker.rank_reels = lambda videos, preferred_topic=None, preferred_region=None: list(videos)
sys.modules["ml.ranker"] = stub_ranker

stub_reputation = ModuleType("ml.reputation")
stub_reputation.get_creator_score = lambda creator_id: 100
stub_reputation.update_creator_score = lambda creator_id, signal: 100
sys.modules["ml.reputation"] = stub_reputation

from app import app
from database import db
from models.user import User
from models.video import Video
from models.voice_reply import VoiceReply


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id


def run_check():
    with app.app_context():
        app.config["TESTING"] = True
        db.drop_all()
        db.create_all()

        creator = User(username="m75_creator", email="m75_creator@example.com", password="secret123")
        listener = User(username="m75_listener", email="m75_listener@example.com", password="secret123")
        db.session.add_all([creator, listener])
        db.session.commit()

        video = Video(
            creator_id=creator.id,
            title="Stability check",
            caption="Testing duplicate-safe replies",
            description="M7.5 verification",
            video_path="/static/uploads/videos/stability.mp4",
            topic="testing",
            region="Durban",
        )
        db.session.add(video)
        db.session.commit()

        client = app.test_client()

        unauth_like = client.post(
            f"/api/videos/{video.id}/like",
            headers={"Accept": "application/json", "X-Requested-With": "fetch"},
        )
        unauth_payload = unauth_like.get_json()
        assert unauth_like.status_code == 401
        assert unauth_payload["code"] == "auth_required"
        assert unauth_payload["login_url"] == "/"

        login_as(client, listener.id)

        token = "voice-reply-token-1"
        response_one = client.post(
            "/voice/reply",
            data={
                "video_id": str(video.id),
                "duration": "10",
                "language_code": "en",
                "client_token": token,
                "voice": (io.BytesIO(b"audio-one"), "reply.wav"),
            },
            content_type="multipart/form-data",
            headers={"Accept": "application/json", "X-Requested-With": "fetch", "X-Idempotency-Key": token},
        )
        payload_one = response_one.get_json()
        assert response_one.status_code == 200
        assert payload_one["reply"]["client_token"] == token
        assert payload_one["deduplicated"] is False

        response_two = client.post(
            "/voice/reply",
            data={
                "video_id": str(video.id),
                "duration": "10",
                "language_code": "en",
                "client_token": token,
                "voice": (io.BytesIO(b"audio-one"), "reply.wav"),
            },
            content_type="multipart/form-data",
            headers={"Accept": "application/json", "X-Requested-With": "fetch", "X-Idempotency-Key": token},
        )
        payload_two = response_two.get_json()
        assert response_two.status_code == 200
        assert payload_two["reply_id"] == payload_one["reply_id"]
        assert payload_two["deduplicated"] is True
        assert VoiceReply.query.filter_by(video_id=video.id, user_id=listener.id).count() == 1

        login_as(client, creator.id)
        room_response = client.post(
            "/api/rooms",
            json={"title": "Stable room", "video_id": video.id, "room_type": "public"},
            headers={"Accept": "application/json", "X-Requested-With": "fetch"},
        )
        room_payload = room_response.get_json()
        assert room_response.status_code == 200
        room_id = room_payload["room"]["id"]

        login_as(client, listener.id)
        room_token = "room-reply-token-1"
        room_reply_one = client.post(
            f"/api/rooms/{room_id}/reply",
            data={
                "duration": "7",
                "language_code": "en",
                "client_token": room_token,
                "voice": (io.BytesIO(b"room-audio"), "room.wav"),
            },
            content_type="multipart/form-data",
            headers={"Accept": "application/json", "X-Requested-With": "fetch", "X-Idempotency-Key": room_token},
        )
        room_reply_payload_one = room_reply_one.get_json()
        assert room_reply_one.status_code == 200
        assert room_reply_payload_one["deduplicated"] is False

        room_reply_two = client.post(
            f"/api/rooms/{room_id}/reply",
            data={
                "duration": "7",
                "language_code": "en",
                "client_token": room_token,
                "voice": (io.BytesIO(b"room-audio"), "room.wav"),
            },
            content_type="multipart/form-data",
            headers={"Accept": "application/json", "X-Requested-With": "fetch", "X-Idempotency-Key": room_token},
        )
        room_reply_payload_two = room_reply_two.get_json()
        assert room_reply_two.status_code == 200
        assert room_reply_payload_two["reply_id"] == room_reply_payload_one["reply_id"]
        assert room_reply_payload_two["deduplicated"] is True

        print("auth_error_contract", "ok")
        print("voice_reply_idempotency", "ok")
        print("premium_room_reply_idempotency", "ok")
        print("m7_5_stability_status", "ok")


if __name__ == "__main__":
    run_check()