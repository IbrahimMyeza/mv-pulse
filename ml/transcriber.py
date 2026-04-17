def transcribe_audio(audio_path):
    import speech_recognition as sr

    recognizer = sr.Recognizer()

    with sr.AudioFile(audio_path) as source:
        audio = recognizer.record(source)

    try:
        return recognizer.recognize_google(audio)
    except Exception:
        return ""