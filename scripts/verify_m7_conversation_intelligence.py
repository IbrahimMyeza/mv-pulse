import io
import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERIFY_DB = ROOT / "instance" / f"m7_conversation_intelligence_{os.getpid()}.db"
VERIFY_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{VERIFY_DB.as_posix()}"
os.environ["MV_M7_DISABLE_ASYNC"] = "1"
warnings.filterwarnings("ignore", category=DeprecationWarning, message=r"datetime\.datetime\.utcnow\(\) is deprecated")

stub_transcriber = ModuleType("ml.transcriber")
stub_transcriber.transcribe_audio = lambda path: "Politics on campus is getting intense and everybody is reacting right now"
sys.modules["ml.transcriber"] = stub_transcriber

stub_sentiment = ModuleType("ml.voice_sentiment")
stub_sentiment.analyze_voice_sentiment = lambda text: 0.48
sys.modules["ml.voice_sentiment"] = stub_sentiment

stub_debate = ModuleType("ml.debate_detector")
stub_debate.controversy_score = lambda sentiment, transcript: 0.61
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
from models.thread_summary import ThreadSummary
from models.user import User
from models.video import Video
from models.voice_embedding import VoiceEmbedding
from models.voice_insight import VoiceInsight
from models.voice_reply import VoiceReply
from services.ai_pipeline import process_voice_reply
from services.social_retention import retention_rank_videos
from services.thread_intelligence import search_discovery
from services.voice_identity import voice_identity_payload


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id


def run_check():
    with app.app_context():
        app.config["TESTING"] = True
        db.drop_all()
        db.create_all()

        creator = User(username="m7_creator", email="m7_creator@example.com", password="secret123")
        listener = User(username="m7_listener", email="m7_listener@example.com", password="secret123")
        db.session.add_all([creator, listener])
        db.session.commit()

        primary_video = Video(
            creator_id=creator.id,
            title="Campus debate",
            caption="Students are arguing about politics on campus",
            description="M7 verification thread",
            video_path="/static/uploads/videos/campus.mp4",
            topic="campus",
            region="Durban",
            created_at=datetime.utcnow() - timedelta(minutes=30),
        )
        secondary_video = Video(
            creator_id=creator.id,
            title="Quiet update",
            caption="A low activity control video",
            description="Baseline retention comparator",
            video_path="/static/uploads/videos/quiet.mp4",
            topic="general",
            region="Durban",
            created_at=datetime.utcnow() - timedelta(hours=4),
        )
        db.session.add_all([primary_video, secondary_video])
        db.session.commit()

        client = app.test_client()
        login_as(client, listener.id)

        post_response = client.post(
            "/voice/reply",
            data={
                "video_id": str(primary_video.id),
                "duration": "14.5",
                "language_code": "en",
                "voice": (io.BytesIO(b"fake-audio"), "reply.wav"),
            },
            content_type="multipart/form-data",
            headers={"Accept": "application/json", "X-Requested-With": "fetch"},
        )
        assert post_response.status_code == 200
        reply_id = post_response.get_json()["reply_id"]

        process_voice_reply(reply_id)

        reply = VoiceReply.query.get(reply_id)
        assert reply is not None
        embedding = VoiceEmbedding.query.filter_by(voice_reply_id=reply_id).first()
        insight = VoiceInsight.query.filter_by(voice_reply_id=reply_id).first()
        summary = ThreadSummary.query.filter_by(video_id=primary_video.id, root_reply_id=None).first()
        assert embedding is not None
        assert insight is not None
        assert summary is not None
        assert insight.processing_state in {"complete", "partial"}

        ranked = retention_rank_videos([secondary_video, primary_video], viewer=listener)
        assert ranked[0].id == primary_video.id

        discovery_items = search_discovery(query="politics", topic="campus")
        assert discovery_items

        identity = voice_identity_payload(listener)
        assert identity["total_processed_replies"] >= 1
        assert identity["dominant_topics"]

        summary_response = client.get(f"/api/thread/{primary_video.id}/summary")
        assert summary_response.status_code == 200
        assert summary_response.get_json()["cluster_label"]

        discovery_response = client.get("/api/discovery?q=politics&topic=campus")
        assert discovery_response.status_code == 200
        assert discovery_response.get_json()["items"]

        identity_response = client.get(f"/api/profile/{listener.username}/voice-identity")
        assert identity_response.status_code == 200
        assert identity_response.get_json()["total_processed_replies"] >= 1

        clips_response = client.get(f"/api/videos/{primary_video.id}/clip-suggestions")
        assert clips_response.status_code == 200
        assert clips_response.get_json()["items"]

        profile_page = client.get(f"/profile/{listener.username}")
        assert profile_page.status_code == 200
        assert b"Conversation Intelligence Core" in profile_page.data

        video_page = client.get(f"/video/{primary_video.id}")
        assert video_page.status_code == 200
        assert b"Auto clip suggestions" in video_page.data

        print("voice_reply_posting", "ok")
        print("voice_embedding_rows", VoiceEmbedding.query.count())
        print("voice_insight_rows", VoiceInsight.query.count())
        print("thread_summary_rows", ThreadSummary.query.count())
        print("discovery_hits", len(discovery_items))
        print("identity_topics", [item["label"] for item in identity["dominant_topics"]])
        print("m7_conversation_intelligence_status", "ok")


if __name__ == "__main__":
    run_check()