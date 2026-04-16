import os
import sys
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERIFY_DB = ROOT / "instance" / f"retention_verify_{os.getpid()}.db"
VERIFY_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{VERIFY_DB.as_posix()}"

stub_transcriber = ModuleType("ml.transcriber")
stub_transcriber.transcribe_audio = lambda path: "Retention verifier transcript"
sys.modules["ml.transcriber"] = stub_transcriber

stub_sentiment = ModuleType("ml.voice_sentiment")
stub_sentiment.analyze_voice_sentiment = lambda transcript: 0.42
sys.modules["ml.voice_sentiment"] = stub_sentiment

stub_debate = ModuleType("ml.debate_detector")
stub_debate.controversy_score = lambda sentiment, transcript: 0.25
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
        viewer = User(username="viewer", email="viewer@example.com", password="secret123")
        db.session.add_all([creator, viewer])
        db.session.commit()

        boosted_video = Video(
            creator_id=creator.id,
            title="Boosted video",
            caption="This should rank first.",
            description="Retention test primary video",
            video_path="/static/videos/football.mp4",
            created_at=datetime.utcnow(),
        )
        plain_video = Video(
            creator_id=creator.id,
            title="Plain video",
            caption="This should rank lower.",
            description="Retention test secondary video",
            video_path="/static/videos/politics.mp4",
            created_at=datetime.utcnow() - timedelta(hours=4),
        )
        db.session.add_all([boosted_video, plain_video])
        db.session.commit()

        creator_reply = VoiceReply(
            video_id=boosted_video.id,
            user_id=creator.id,
            audio_url="/static/voices/replies/creator.wav",
            duration=1.0,
            transcript="Creator opens the thread.",
        )
        db.session.add(creator_reply)
        db.session.commit()

        nested_reply = VoiceReply(
            video_id=boosted_video.id,
            user_id=viewer.id,
            parent_reply_id=creator_reply.id,
            audio_url="/static/voices/replies/nested.wav",
            duration=1.6,
            transcript="Nested reply to deepen the thread.",
        )
        db.session.add(nested_reply)
        boosted_video.voice_replies = 2
        db.session.commit()

        client = app.test_client()
        login_as(client, viewer.id)

        follow = client.post(f"/api/follow/{creator.id}")
        assert follow.status_code == 200

        save_video = client.post(f"/api/videos/{boosted_video.id}/save")
        assert save_video.status_code == 200
        assert save_video.get_json()["saved"] is True

        save_reply = client.post(f"/api/voice-replies/{creator_reply.id}/save")
        assert save_reply.status_code == 200
        assert save_reply.get_json()["saved"] is True

        like_video = client.post(f"/api/videos/{boosted_video.id}/like")
        assert like_video.status_code == 200

        like_reply = client.post(f"/api/voice-replies/{creator_reply.id}/like")
        assert like_reply.status_code == 200

        post_reply = client.post(
            "/voice/reply",
            data={
                "video_id": str(boosted_video.id),
                "parent_reply_id": str(creator_reply.id),
                "language_code": "en",
                "duration": "2.0",
                "voice": (BytesIO(b"voice-bytes"), "reply.wav"),
            },
            headers={"Accept": "application/json", "X-Requested-With": "fetch"},
            content_type="multipart/form-data",
        )
        assert post_reply.status_code == 200

        saved_videos = client.get("/api/me/saved/videos")
        saved_replies = client.get("/api/me/saved/replies")
        liked_videos = client.get("/api/me/likes")
        my_replies = client.get("/api/me/voice-replies")
        activity = client.get("/api/me/activity")

        assert saved_videos.status_code == 200
        assert saved_videos.get_json()["items"][0]["id"] == boosted_video.id
        assert saved_replies.status_code == 200
        assert saved_replies.get_json()["items"][0]["id"] == creator_reply.id
        assert liked_videos.status_code == 200
        assert liked_videos.get_json()["items"][0]["id"] == boosted_video.id
        assert my_replies.status_code == 200
        assert len(my_replies.get_json()["items"]) >= 2
        assert activity.status_code == 200
        assert any(item["kind"] == "save_video" for item in activity.get_json()["items"])

        feed = client.get("/api/feed")
        assert feed.status_code == 200
        assert feed.get_json()["videos"][0]["id"] == boosted_video.id

        older_notification = Notification(
            recipient_user_id=creator.id,
            kind="export_ready",
            message="Your export is ready.",
            created_at=datetime.utcnow() - timedelta(days=8),
        )
        weekly_notification = Notification(
            recipient_user_id=creator.id,
            kind="weekly_digest",
            message="Your weekly voice digest is ready.",
            created_at=datetime.utcnow() - timedelta(days=3),
        )
        db.session.add_all([older_notification, weekly_notification])
        db.session.commit()

        creator_client = app.test_client()
        login_as(creator_client, creator.id)

        profile_page = creator_client.get(f"/profile/{creator.username}")
        assert profile_page.status_code == 200
        assert b"Retention Library" in profile_page.data
        assert b"Saved Replies" in profile_page.data

        notifications_page = creator_client.get("/notifications")
        assert notifications_page.status_code == 200
        assert b"Today" in notifications_page.data
        assert b"This week" in notifications_page.data
        assert b"Older" in notifications_page.data
        assert f"/video/{boosted_video.id}#reply-".encode() in notifications_page.data

        unread_before = creator_client.get("/api/feed").get_json()["notifications_unread_count"]
        assert unread_before >= 1

        mark_read = creator_client.post("/api/notifications/read", json={})
        assert mark_read.status_code == 200
        assert mark_read.get_json()["unread_count"] == 0

        unread_after = creator_client.get("/api/feed").get_json()["notifications_unread_count"]
        assert unread_after == 0

        print("saved_videos", len(saved_videos.get_json()["items"]))
        print("saved_replies", len(saved_replies.get_json()["items"]))
        print("my_voice_replies", len(my_replies.get_json()["items"]))
        print("activity_items", len(activity.get_json()["items"]))
        print("feed_top_video", feed.get_json()["videos"][0]["id"])
        print("notifications_grouped", True)
        print("unread_after_read", unread_after)
        print("retention_status", "ok")


if __name__ == "__main__":
    run_check()