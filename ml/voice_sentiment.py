from textblob import TextBlob

def analyze_voice_sentiment(text):
    sentiment = TextBlob(text).sentiment.polarity
    return sentiment