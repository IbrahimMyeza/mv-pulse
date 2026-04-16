def learn_preferences(user, reel):
    if not hasattr(user, "preferred_topic"):
        user.preferred_topic = getattr(reel, "topic", "general")

    if not hasattr(user, "preferred_region"):
        user.preferred_region = getattr(reel, "region", "Durban")

    if getattr(reel, "topic", "general") == getattr(user, "preferred_topic", "general"):
        user.topic_affinity = getattr(user, "topic_affinity", 1.0) + 0.1
    else:
        user.topic_affinity = max(getattr(user, "topic_affinity", 1.0) - 0.05, 0.5)

    return user