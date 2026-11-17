from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DateTime, Integer, JSON, MetaData, Table, func, select, text, update
from sqlalchemy.engine import Connection, Engine, create_engine
from sqlalchemy.pool import StaticPool

from backend.services.data_store import store


_PERSISTED_COLLECTIONS = (
    "users_by_id",
    "sessions",
    "assessment_results",
    "assessment_sessions",
    "resume_data",
    "user_target_roles",
    "roadmap_progress",
    "admin_sessions",
    "admin_companies",
    "admin_roles",
    "admin_role_index",
    "company_role_requirements",
    "admin_questions",
    "admin_custom_tests",
    "admin_role_test_assignments",
    "admin_student_test_assignments",
    "admin_role_roadmap_overrides",
    "admin_student_roadmap_assignments",
    "admin_student_resource_recommendations",
    "career_paths",
    "question_bank",
)

_metadata = MetaData()
_application_state = Table(
    "application_state",
    _metadata,
    Column("id", Integer, primary_key=True),
    Column("state", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


class ApplicationStatePersistence:
    """Persist the MVP's shared application state in a single database snapshot."""

    def __init__(self, database_url: str) -> None:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

        engine_options: dict[str, Any] = {"pool_pre_ping": True}
        if database_url.startswith("sqlite:"):
            engine_options["connect_args"] = {"check_same_thread": False}
            if database_url in {"sqlite://", "sqlite:///:memory:"}:
                engine_options["poolclass"] = StaticPool
        self.engine: Engine = create_engine(database_url, **engine_options)

    def initialize(self) -> None:
        _metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": 824721006531})
            state = connection.execute(
                select(_application_state.c.id).where(_application_state.c.id == 1)
            ).scalar_one_or_none()
            if state is None:
                if os.getenv("MIGRATE_LEGACY_AUTH_DATA") == "1":
                    self._import_legacy_users()
                connection.execute(
                    _application_state.insert().values(id=1, state=self._snapshot())
                )

    @staticmethod
    def _import_legacy_users() -> None:
        if os.getenv("APP_ENV", "development") == "test":
            return

        legacy_path = Path(__file__).with_name("auth_data.json")
        if not legacy_path.exists():
            return

        with legacy_path.open(encoding="utf-8") as file:
            payload = json.load(file)
        for user in payload.get("users", []):
            user_id = user.get("id")
            email = user.get("email")
            if not user_id or not email:
                continue
            store.users_by_id[user_id] = user
            store.users_by_email[email] = user
            student_id = user.get("student_id")
            if student_id:
                store.users_by_student_id[student_id] = user

        store.sessions.clear()

    def begin_request(self) -> Connection:
        connection = self.engine.connect()
        try:
            connection.begin()
            if connection.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": 824721006531})
        except Exception:
            connection.close()
            raise
        return connection

    @staticmethod
    def _snapshot() -> dict[str, Any]:
        state = {name: getattr(store, name) for name in _PERSISTED_COLLECTIONS}
        serialized = json.dumps(state, default=lambda value: sorted(value) if isinstance(value, set) else str(value))
        return json.loads(serialized)

    @staticmethod
    def _restore(snapshot: dict[str, Any]) -> None:
        for name in _PERSISTED_COLLECTIONS:
            target = getattr(store, name)
            target.clear()
            target.update(snapshot.get(name, {}))

        store.users_by_email.clear()
        store.users_by_student_id.clear()
        for user in store.users_by_id.values():
            email = user.get("email")
            student_id = user.get("student_id")
            if email:
                store.users_by_email[email] = user
            if student_id:
                store.users_by_student_id[student_id] = user

        for session in store.assessment_sessions.values():
            if "asked_ids" in session and isinstance(session["asked_ids"], list):
                session["asked_ids"] = set(session["asked_ids"])

    def load(self, connection: Connection) -> None:
        snapshot = connection.execute(
            select(_application_state.c.state).where(_application_state.c.id == 1)
        ).scalar_one_or_none()
        if snapshot is not None:
            self._restore(snapshot)

    def save(self, connection: Connection) -> None:
        snapshot = self._snapshot()
        result = connection.execute(
            update(_application_state)
            .where(_application_state.c.id == 1)
            .values(state=snapshot, updated_at=func.now())
        )
        if result.rowcount == 0:
            connection.execute(_application_state.insert().values(id=1, state=snapshot))
        connection.commit()

    @staticmethod
    def rollback(connection: Connection) -> None:
        connection.rollback()

    @staticmethod
    def close(connection: Connection) -> None:
        connection.close()

    def check(self) -> bool:
        with self.engine.connect() as connection:
            return connection.execute(text("SELECT 1")).scalar_one() == 1


_database_url = os.getenv("DATABASE_URL")
_use_database = bool(_database_url) and os.getenv("APP_ENV", "development") != "test"
persistence = ApplicationStatePersistence(_database_url) if _use_database and _database_url else None
