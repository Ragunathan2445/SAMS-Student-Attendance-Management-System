"""Integration tests run against a *separate* database given in TEST_DATABASE_URL
(they migrate it and reseed it). Without TEST_DATABASE_URL only unit tests run."""
import os

if os.getenv("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ.setdefault("MONGO_DB_NAME", "sams_logs_test")
os.environ.setdefault("ENABLE_DEMO_OTP_INBOX", "true")
os.environ.setdefault("ALLOW_OFF_HOURS_TEACHER_LOGIN", "true")
os.environ.setdefault("LOGIN_RATE_LIMIT_PER_MINUTE", "1000")
