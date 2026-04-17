# mv-pulse
AI-powered predictive media intelligence and creator studio SaaS built with Flask.

## Persistence notes

- Accounts and application data live in the configured SQL database.
- Uploaded videos and voice files should use `MEDIA_STORAGE_ROOT` so media survives redeploys.
- On Render, `render.yaml` mounts a persistent disk at `/var/data` and points `MEDIA_STORAGE_ROOT` there.
- Sessions are configured as permanent cookies with a configurable lifetime via `SESSION_DAYS`.
