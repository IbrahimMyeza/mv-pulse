def controversy_score(sentiment, transcript):
    score = abs(sentiment) * 10

    hot_words = [
        "wrong",
        "truth",
        "debate",
        "facts",
        "war",
        "religion",
        "politics",
        "Israel",
        "Palestine",
        "Kaizer Chiefs",
        "Orlando Pirates"
    ]

    text = transcript.lower()

    for word in hot_words:
        if word.lower() in text:
            score += 5

    return score