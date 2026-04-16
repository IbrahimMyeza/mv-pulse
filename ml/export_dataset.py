import csv
import os
from models.reel import Reel

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "reels_dataset.csv")


def export_reels_dataset():
    reels = Reel.query.all()

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow([
            "id",
            "title",
            "likes",
            "views",
            "watch_time",
            "comments",
            "category"
        ])

        for reel in reels:
            writer.writerow([
                reel.id,
                reel.title,
                reel.likes,
                reel.views,
                reel.watch_time,
                reel.comments,
                getattr(reel, "category", "general")
            ])