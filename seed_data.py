from app import app, db
from models.reel import Reel


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


if __name__ == "__main__":
    with app.app_context():
        seed_demo_reels()