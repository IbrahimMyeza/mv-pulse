import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERIFY_DB = ROOT / "instance" / f"thread_heat_verify_{os.getpid()}.db"
VERIFY_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{VERIFY_DB.as_posix()}"

stub_transcriber = ModuleType("ml.transcriber")
stub_transcriber.transcribe_audio = lambda path: "Thread propagation verifier transcript"
sys.modules["ml.transcriber"] = stub_transcriber

stub_sentiment = ModuleType("ml.voice_sentiment")
stub_sentiment.analyze_voice_sentiment = lambda transcript: 0.5
sys.modules["ml.voice_sentiment"] = stub_sentiment

stub_debate = ModuleType("ml.debate_detector")
stub_debate.controversy_score = lambda sentiment, transcript: 0.3
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
from models.notification import Notification
from models.save import Save
from models.user import User
from models.video import Video
from models.voice_reply import VoiceReply


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id


def run_check():
    with app.app_context():
        db.drop_all()
        db.create_all()

        creator = User(username="creator", email="creator@example.com", password="secret123")
        alpha = User(username="alpha_voice", email="alpha@example.com", password="secret123")
        beta = User(username="beta_voice", email="beta@example.com", password="secret123")
        gamma = User(username="gamma_voice", email="gamma@example.com", password="secret123")
        db.session.add_all([creator, alpha, beta, gamma])
        db.session.commit()

        hot_video = Video(
            creator_id=creator.id,
            title="Hot debate reel",
            caption="This thread should re-enter the feed.",
            description="Hot thread fixture",
            video_path="/static/videos/football.mp4",
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
        plain_video = Video(
            creator_id=creator.id,
            title="Cold reel",
            caption="This one should stay normal.",
            description="Cold fixture",
            video_path="/static/videos/politics.mp4",
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        older_video = Video(
            creator_id=creator.id,
            title="Archive reel",
            caption="Older conversation.",
            description="Archive fixture",
            video_path="/static/videos/football.mp4",
            created_at=datetime.utcnow() - timedelta(hours=5),
        )
        db.session.add_all([hot_video, plain_video, older_video])
        db.session.commit()

        root_reply = VoiceReply(
            video_id=hot_video.id,
            user_id=creator.id,
            audio_url="/static/voices/replies/root.wav",
            duration=1.2,
            transcript="Root reply",
            created_at=datetime.utcnow() - timedelta(minutes=50),
        )
        second_reply = VoiceReply(
            video_id=hot_video.id,
            user_id=alpha.id,
            parent_reply=root_reply,
            audio_url="/static/voices/replies/alpha.wav",
            duration=1.4,
            transcript="Second level reply",
            created_at=datetime.utcnow() - timedelta(minutes=35),
        )
        third_reply = VoiceReply(
            video_id=hot_video.id,
            user_id=beta.id,
            parent_reply=second_reply,
            audio_url="/static/voices/replies/beta.wav",
            duration=1.6,
            transcript="Third level reply",
            created_at=datetime.utcnow() - timedelta(minutes=10),
        )
        extra_reply = VoiceReply(
            video_id=hot_video.id,
            user_id=gamma.id,
            parent_reply=root_reply,
            audio_url="/static/voices/replies/gamma.wav",
            duration=1.8,
            transcript="Another voice joins",
            created_at=datetime.utcnow() - timedelta(minutes=5),
        )
        db.session.add_all([root_reply, second_reply, third_reply, extra_reply])
        hot_video.voice_replies = 4
        db.session.commit()

        alpha_client = app.test_client()
        beta_client = app.test_client()
        creator_client = app.test_client()
        anonymous_client = app.test_client()

        login_as(alpha_client, alpha.id)
        login_as(beta_client, beta.id)
        login_as(creator_client, creator.id)

        alpha_client.post(f"/api/follow/{creator.id}")
        beta_client.post(f"/api/follow/{creator.id}")
        alpha_client.post(f"/api/videos/{hot_video.id}/save")
        alpha_client.post(f"/api/voice-replies/{root_reply.id}/save")

        for _ in range(3):
            anonymous_client.post(f"/api/voice-replies/{root_reply.id}/listen")
        for _ in range(2):
            anonymous_client.post(f"/api/voice-replies/{second_reply.id}/listen")

        feed = anonymous_client.get("/api/feed")
        assert feed.status_code == 200
        payload = feed.get_json()
        hot_cards = [item for item in payload["feed_items"] if item["kind"] == "hot_thread"]
        assert hot_cards, "expected at least one injected hot thread card"
        hot_card = hot_cards[0]
        assert hot_card["reel_id"] == hot_video.id
        assert "focus_reply_id" in hot_card["target_url"]

        duplicate_check = anonymous_client.get("/api/feed").get_json()
        duplicate_cards = [item for item in duplicate_check["feed_items"] if item["kind"] == "hot_thread" and item["reel_id"] == hot_video.id]
        assert len(duplicate_cards) == 1

        trending_notifications = Notification.query.filter_by(kind="thread_trending", video_id=hot_video.id).all()
        assert len(trending_notifications) >= 3
        notification_count = len(trending_notifications)

        anonymous_feed_page = anonymous_client.get("/feed")
        assert anonymous_feed_page.status_code == 200
        assert b"People are talking about this right now" in anonymous_feed_page.data

        focused_page = anonymous_client.get(hot_card["target_url"])
        assert focused_page.status_code == 200
        assert f'data-focus-reply-id="{hot_card["highlighted_reply_id"]}"'.encode() in focused_page.data
        assert f'id="reply-{hot_card["highlighted_reply_id"]}"'.encode() in focused_page.data

        notifications_page = creator_client.get("/notifications")
        assert notifications_page.status_code == 200
        assert b"Your conversation is trending" in notifications_page.data
        assert hot_card["target_url"].encode() in notifications_page.data

        auth_video_page = alpha_client.get(hot_card["target_url"])
        assert auth_video_page.status_code == 200
        assert b"Record voice reply" in auth_video_page.data

        second_notification_pass = anonymous_client.get("/api/feed")
        assert second_notification_pass.status_code == 200
        assert Notification.query.filter_by(kind="thread_trending", video_id=hot_video.id).count() == notification_count

        print("hot_thread_cards", len(hot_cards))
        print("highlighted_reply", hot_card["highlighted_reply_id"])
        print("notification_count", notification_count)
        print("anonymous_cta", True)
        print("focused_target", hot_card["target_url"])
        print("thread_propagation_status", "ok")


if __name__ == "__main__":
    run_check()