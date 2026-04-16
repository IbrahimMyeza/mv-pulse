from app import app, db
from models.reel import Reel
from models.video import Video


def seed_demo_reels():
    if Reel.query.count() > 0:
        print("Demo reels already exist. Skipping seed.")
        return

    demo_reels = [
        Reel(
            title="Durban football rivalry debate",
            video_path="static/videos/football.mp4",
            likes=120,
            views=1500,
            watch_time=300,
            comments=40,
            creator_score=1.8,
            report_count=0,
            voice_replies=12,
            emotion_score=1.5,
            debate_score=2.0,
            topic="sports",
            community_score=1.7,
            region="Durban"
        ),
        Reel(
            title="Campus politics voice clash",
            video_path="static/videos/politics.mp4",
            likes=90,
            views=1100,
            watch_time=280,
            comments=55,
            creator_score=1.3,
            report_count=1,
            voice_replies=20,
            emotion_score=1.8,
            debate_score=2.5,
            topic="politics",
            community_score=1.9,
            region="Durban"
        )
    ]

    db.session.add_all(demo_reels)
    db.session.commit()
    print("Demo reels inserted successfully.")


def seed_demo_videos():
    if Video.query.count() > 0:
        print("Demo videos already exist. Skipping social seed.")
        return

    demo_videos = [
        Video(
            title="Umbono Wami street debate",
            caption="What does Durban think about creator culture right now? Reply with your voice.",
            description="Seed social video for Umbono Wami voice-first discussions.",
            video_path="/static/videos/football.mp4",
            topic="community",
            region="Durban",
            category="community",
            likes=48,
            views=640,
            comments=6,
            voice_replies=6,
            creator_score=1.3,
            debate_score=1.1,
            community_score=1.4,
            language_code="en",
        ),
        Video(
            title="Campus voice notes only",
            caption="isiZulu or English, say your piece with a voice note.",
            description="Seed social video for bilingual voice-first reply threads.",
            video_path="/static/videos/politics.mp4",
            topic="campus",
            region="Durban",
            category="campus",
            likes=56,
            views=720,
            comments=8,
            voice_replies=8,
            creator_score=1.5,
            debate_score=1.6,
            community_score=1.5,
            language_code="zu",
        ),
    ]

    db.session.add_all(demo_videos)
    db.session.commit()
    print("Demo videos inserted successfully.")


if __name__ == "__main__":
    with app.app_context():
        seed_demo_reels()
        seed_demo_videos()