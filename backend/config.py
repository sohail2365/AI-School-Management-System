from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "School Management System"
    DEBUG: bool = False

    DATABASE_URL: str = "sqlite:///./school.db"

    JWT_SECRET: str = "replace_with_a_strong_random_secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 4320  # 3 days

    CORS_ORIGINS: str = "*"
    LOG_FILE: str = "logs/app.log"
    API_V1_PREFIX: str = "/api/v1"

    # Email (used for password reset). Optional — if not configured, the
    # forgot-password endpoint still works but logs the reset link to the
    # server console instead of emailing it (fine for local dev/testing;
    # set these for real deployments so users actually receive the email).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "School Hub"

    # Used to build the password reset link sent in the email.
    # e.g. https://schoolhub-ivory.vercel.app
    FRONTEND_BASE_URL: str = "http://127.0.0.1:8000"

    # Platform-owner access (super admin panel) — completely separate from
    # normal school logins. Set this to a long random value in production;
    # anyone with this key can see/deactivate/delete ANY school's account.
    SUPER_ADMIN_SECRET: str = ""

    # AI features (student summaries / class reports) via Groq. Optional —
    # if not set, AI endpoints return a clear "not configured" message and
    # everything else keeps working normally.
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Supabase Storage (for student photos, ID cards, B-forms, test paper
    # scans). Vercel's filesystem is ephemeral/read-only at runtime, so
    # uploaded files CANNOT be saved to local disk — they must go to an
    # external object store. Uses the same Supabase project as the database.
    # Get these from Supabase dashboard -> Project Settings -> API:
    #   SUPABASE_URL = https://<project-ref>.supabase.co
    #   SUPABASE_SERVICE_KEY = the "service_role" secret key (NOT the anon key —
    #     the service role key is required to upload from the backend and
    #     must never be exposed to the frontend/browser)
    # Then create a bucket named "student-files" (Storage -> New bucket).
    # If these are not set, upload endpoints return a clear "not configured"
    # error and everything else keeps working normally.
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_BUCKET: str = "student-files"

    # Error monitoring via Sentry (sentry.io, free tier). Optional — if not
    # set, Sentry stays disabled and nothing changes. Set SENTRY_DSN in
    # Vercel env vars (both Production and Preview) to enable.
    # SENTRY_ENVIRONMENT distinguishes production errors from staging ones
    # in the Sentry dashboard — set it to "production" / "staging" per env.
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "production"

    # Backup export endpoint (/backup/export) is protected by this secret,
    # sent as the X-Backup-Secret header. If empty, the endpoint is disabled
    # (returns 503) so data is never exposed by accident. Set a long random
    # value in Vercel env vars to enable scheduled backups.
    BACKUP_SECRET: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
