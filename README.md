# mv-pulse
AI-powered predictive media intelligence and creator studio SaaS built with Flask.

## Persistence notes

- Production uses the Render `DATABASE_URL` and requires PostgreSQL; local development can still use `LOCAL_DATABASE_URL`.
- Render runs schema changes through `flask --app app db upgrade` before each deploy.
- Uploaded videos, voice replies, avatars, thumbnails, and other future media assets use `CLOUDINARY_URL` when configured, storing permanent secure URLs in the database.
- `MEDIA_STORAGE_ROOT` remains available as a local or emergency fallback when Cloudinary is not configured.
- Sessions use a stable `SECRET_KEY`, secure cookies, and configurable persistence via `SESSION_DAYS`.
- Demo content seeding is startup-driven via `AUTO_SEED_DEMO_DATA` instead of a build-time seed step.
