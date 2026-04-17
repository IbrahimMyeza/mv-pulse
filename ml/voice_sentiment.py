def analyze_voice_sentiment(text):
    if not text:
        return 0.0

    try:
        from textblob import TextBlob
    except Exception:
        return 0.0

    try:
        return TextBlob(text).sentiment.polarity
    except Exception:
        return 0.0