import csv
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "reels_dataset.csv")

X = []
y = []

# Create sample data if CSV is empty
if not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0:
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "title", "likes", "views", "watch_time", "comments", "category"])
        for i in range(100):
            writer.writerow([i, f"Reel {i}", 100+i*5, 1000+i*20, 10+i*0.5, 5+i, "general"])

with open(CSV_PATH, "r", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    for row in reader:
        likes = int(row["likes"])
        views = int(row["views"])
        watch_time = float(row["watch_time"])
        comments = int(row["comments"])

        virality_score = likes * 3 + views + watch_time * 2 + comments

        X.append([likes, views, watch_time, comments])
        y.append(virality_score)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = RandomForestRegressor()
model.fit(X_train, y_train)

predictions = model.predict(X_test)
error = mean_absolute_error(y_test, predictions)

print("MAE:", error)
print("Sample prediction:", predictions[:5])