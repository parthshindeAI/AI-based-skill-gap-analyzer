from __future__ import annotations

import io
import os
import uuid
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from backend.api.main import _validate_deployment_config, app
from backend.services.data_store import store
from backend.services.persistence import ApplicationStatePersistence


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def register_student(client: TestClient, role: str = "AI Engineer") -> tuple[dict, dict]:
    student_id = f"STU{uuid.uuid4().hex[:10].upper()}"
    response = client.post(
        "/api/register",
        json={
            "name": "Portfolio Student",
            "email": f"student-{uuid.uuid4().hex[:10]}@example.com",
            "student_id": student_id,
            "password": "StrongStudentPass123!",
            "target_role": role,
            "current_skills": ["Python"],
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data, {"Authorization": f"Bearer {data['access_token']}"}


def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/admin/login",
        json={
            "username": os.getenv("ADMIN_USERNAME", "test_admin"),
            "password": os.getenv("ADMIN_PASSWORD", "TestOnly-Admin-Password-123!"),
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_student_workflows_and_resume_features(client: TestClient) -> None:
    student, headers = register_student(client)

    assert client.get("/api/profile", headers=headers).status_code == 200
    assert client.get("/api/career-paths").status_code == 200
    assert client.get("/api/assessment/start", headers=headers).status_code == 200
    assert client.post(
        "/api/assessment/submit",
        headers=headers,
        json={"scores": {"Python": 80, "Statistics": 60, "Machine Learning": 45, "Deep Learning": 40}},
    ).status_code == 200
    assert client.get("/api/assessment/result", headers=headers).status_code == 200
    assert client.get("/api/skill-gap/analyze", headers=headers).status_code == 200
    assert client.get("/api/roadmap", headers=headers).status_code == 200

    progress = client.get("/api/progress", headers=headers)
    assert progress.status_code == 200
    assert client.post(
        "/api/progress/complete",
        headers=headers,
        json={"skill": "Python", "stage": "beginner"},
    ).status_code == 200
    assert client.delete("/api/progress/reset", headers=headers).status_code == 200

    pdf_buffer = io.BytesIO()
    pdf = canvas.Canvas(pdf_buffer)
    pdf.drawString(72, 720, student["user"]["name"])
    pdf.drawString(72, 690, student["user"]["email"])
    pdf.drawString(72, 660, "Python SQL pandas")
    pdf.save()
    parsed = client.post(
        "/api/resume/parse",
        headers=headers,
        files={"file": ("resume.pdf", pdf_buffer.getvalue(), "application/pdf")},
    )
    assert parsed.status_code == 200, parsed.text

    preview = client.post("/api/resume/preview", headers=headers, json={"projects": [{"name": "Portfolio", "tech": ["Python"]}]})
    assert preview.status_code == 200, preview.text
    generated = client.post("/api/resume/generate", headers=headers, json={})
    assert generated.status_code == 200
    assert generated.headers["content-type"].startswith("application/pdf")

    adaptive = client.post("/api/assessment/adaptive/start", headers=headers)
    assert adaptive.status_code == 200, adaptive.text
    question_id = adaptive.json()["question"]["id"]
    answer = client.post(
        "/api/assessment/adaptive/answer",
        headers=headers,
        json={"question_id": question_id, "selected": [0]},
    )
    assert answer.status_code == 200, answer.text


def test_admin_crud_and_assignments_are_reflected(client: TestClient) -> None:
    student, student_headers = register_student(client)
    headers = admin_headers(client)
    student_id = student["user"]["student_id"]

    assert client.get("/api/admin/snapshot", headers=headers).status_code == 200
    assert client.get("/api/admin/students", headers=headers).status_code == 200
    assert client.get("/api/admin/snapshot").status_code == 401

    role_name = f"Portfolio QA {uuid.uuid4().hex[:8]}"
    role_response = client.post(
        "/api/admin/role",
        headers=headers,
        json={"company": "PortfolioCo", "role": role_name, "skills": [{"skill": "SQL", "weight": "High", "minimum_score_required": 75}]},
    )
    assert role_response.status_code == 200, role_response.text
    role_id = role_response.json()["id"]
    renamed_role = f"{role_name} Renamed"
    updated = client.put(f"/api/admin/role/{role_id}", headers=headers, json={"role": renamed_role})
    assert updated.status_code == 200, updated.text
    career_paths = client.get("/api/career-paths").json()["roles"]
    assert role_name not in career_paths
    assert renamed_role in career_paths

    duplicate = client.post(
        "/api/admin/role",
        headers=headers,
        json={"company": "PortfolioCo", "role": renamed_role, "skills": [{"skill": "SQL"}]},
    )
    assert duplicate.status_code == 409

    question_response = client.post(
        "/api/admin/question",
        headers=headers,
        json={
            "question": "Which SQL clause filters rows?",
            "type": "MCQ",
            "skill": "SQL",
            "difficulty": "Medium",
            "weight": 2,
            "options": ["WHERE", "ORDER BY"],
            "correct_answers": [0],
        },
    )
    assert question_response.status_code == 200, question_response.text
    question_id = question_response.json()["id"]
    assert client.get("/api/admin/questions", headers=headers).status_code == 200
    assert client.put(f"/api/admin/question/{question_id}", headers=headers, json={"weight": 3}).status_code == 200

    assigned_test = client.post(
        "/api/admin/tests",
        headers=headers,
        json={"name": "SQL test", "question_ids": [question_id], "student_id": student_id},
    )
    assert assigned_test.status_code == 200, assigned_test.text
    assessment = client.get("/api/assessment/start", headers=student_headers)
    assert assessment.status_code == 200
    assert assessment.json()["source"] == "admin_assigned_test"
    assert assessment.json()["questions"][0]["id"] == question_id

    custom_skill = f"CustomRoadmap{uuid.uuid4().hex[:6]}"
    custom_step = {
        "skill": custom_skill,
        "priority": "High",
        "start_from_stage": "beginner",
        "stages": [{"stage": "beginner", "title": "Custom curriculum", "time_weeks": 1, "tasks": ["Complete a task"]}],
        "total_weeks": 1,
    }
    custom_resource = {"title": "Admin SQL guide", "url": "https://example.com/sql"}
    assert client.post(
        "/api/assessment/submit",
        headers=student_headers,
        json={"scores": {"Python": 40, "Statistics": 30, "Machine Learning": 20, "Deep Learning": 20}},
    ).status_code == 200
    override = client.post(
        "/api/admin/roadmap-override",
        headers=headers,
        json={"role": "AI Engineer", "timeline_weeks": 1, "custom_steps": [custom_step], "custom_resources": [custom_resource]},
    )
    assert override.status_code == 200, override.text
    roadmap = client.get("/api/roadmap", headers=student_headers)
    assert roadmap.status_code == 200, roadmap.text
    assert any(item["skill"] == custom_skill for item in roadmap.json()["roadmap"])
    assert roadmap.json()["roadmap"][0]["custom_resources"] == [custom_resource]

    assigned_step = {**custom_step, "skill": f"AssignedRoadmap{uuid.uuid4().hex[:6]}"}
    assigned_roadmap = client.post(
        "/api/admin/assign-roadmap",
        headers=headers,
        json={"student_id": student_id, "role": "AI Engineer", "timeline_weeks": 1, "custom_steps": [assigned_step]},
    )
    assert assigned_roadmap.status_code == 200, assigned_roadmap.text
    roadmap = client.get("/api/roadmap", headers=student_headers)
    assert any(item["skill"] == assigned_step["skill"] for item in roadmap.json()["roadmap"])

    assert client.delete(f"/api/admin/question/{question_id}", headers=headers).status_code == 200
    assert client.delete(f"/api/admin/role/{role_id}", headers=headers).status_code == 200
    assert renamed_role not in client.get("/api/career-paths").json()["roles"]


def test_production_configuration_rejects_missing_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")

    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        _validate_deployment_config()


def test_postgres_compatible_state_persistence_uses_sqlite_for_isolated_check() -> None:
    persistence = ApplicationStatePersistence("sqlite:///:memory:")
    original_paths = deepcopy(store.career_paths)
    marker = f"PersistenceCheck{uuid.uuid4().hex}"
    try:
        persistence.initialize()
        connection = persistence.begin_request()
        store.career_paths[marker] = {"Python": 77}
        persistence.save(connection)
        persistence.close(connection)

        store.career_paths.pop(marker)
        connection = persistence.begin_request()
        persistence.load(connection)
        assert store.career_paths[marker] == {"Python": 77}
        persistence.rollback(connection)
        persistence.close(connection)
    finally:
        store.career_paths.clear()
        store.career_paths.update(original_paths)
        persistence.engine.dispose()
