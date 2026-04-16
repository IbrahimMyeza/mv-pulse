def diversify_feed(reels, preferred_topic):
    diversified = []
    seen_topics = set()

    for reel in reels:
        if reel.topic not in seen_topics:
            diversified.append(reel)
            seen_topics.add(reel.topic)

    for reel in reels:
        if reel not in diversified:
            diversified.append(reel)

    return diversified