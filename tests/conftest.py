import os


if os.getenv("TEST_DATABASE_BACKEND") == "postgresql":
    if os.getenv("APP_ENV") != "testing" or not os.getenv("DATABASE_URL", "").startswith("postgresql"):
        raise RuntimeError("PostgreSQL test mode requires APP_ENV=testing and a PostgreSQL DATABASE_URL")
else:
    os.environ["APP_ENV"] = "test"
    os.environ.pop("DATABASE_URL", None)

os.environ.setdefault("ADMIN_USERNAME", "test_admin")
os.environ.setdefault("ADMIN_PASSWORD", "TestOnly-Admin-Password-123!")
os.environ.setdefault("MIGRATE_LEGACY_AUTH_DATA", "0")
