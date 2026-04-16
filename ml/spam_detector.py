def spam_penalty(reel):
    text = getattr(reel, "title", "").lower()

    spam_words = ["free money", "click now", "buy now", "win fast", "crypto scam"]

    penalty = 0
    for word in spam_words:
        if word in text:
            penalty += 30

    return penalty