from fastapi.testclient import TestClient
import pytest

from backend.admin.admin_service import AdminService
from backend.api.main import app
from backend.services.assessment_service import AssessmentService
from backend.services.data_store import store
from backend.services.skill_gap_service import SkillGapService


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_case_insensitive_roles_and_role_rename_sync() -> None:
    user = {"id": "case-user", "target_role": "ai engineer", "current_skills": ["Python"]}
    store.career_paths["AI Engineer"] = {"Python": 85, "Machine Learning": 80}
    store.assessment_results[user["id"]] = {"Python": 80, "Machine Learning": 70}

    started = AssessmentService.start_assessment(user)
    assert started["target_role"] == "AI Engineer"

    gap = SkillGapService.analyze(user)
    assert gap["target_role"] == "AI Engineer"

    store.user_target_roles[user["id"]] = "AI Engineer"
    store.admin_roles["role-1"] = {"company": "PortfolioCo", "role": "AI Engineer", "skills": [{"skill": "Python", "weight": "High", "minimum_score_required": 80}]}
    store.admin_role_index["portfolioco::ai engineer"] = "role-1"
    store.admin_student_roadmap_assignments[user["id"]] = {"role": "AI Engineer"}
    store.admin_role_roadmap_overrides["AI Engineer"] = {"role": "AI Engineer", "custom_steps": []}

    AdminService.update_role("role-1", {"role": "AI Engineer Renamed"})

    assert store.user_target_roles[user["id"]] == "AI Engineer Renamed"
    assert store.admin_student_roadmap_assignments[user["id"]]["role"] == "AI Engineer Renamed"
    assert "AI Engineer Renamed" in store.admin_role_roadmap_overrides


def test_auth_assessment_and_skill_gap_flow(client: TestClient) -> None:
    register_payload = {
        "name": "Student One",
        "email": "student1@example.com",
        "password": "secure123",
        "education_level": "Undergraduate",
        "current_skills": ["Python", "Basic Math"],
        "target_role": "AI Engineer",
        "learning_goals": ["Become ML Engineer"],
    }
    register_response = client.post("/api/register", json=register_payload)
    assert register_response.status_code == 200

    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assessment_start = client.get("/api/assessment/start", headers=headers)
    assert assessment_start.status_code == 200
    assert assessment_start.json()["target_role"] == "AI Engineer"

    submit_payload = {
        "scores": {
            "Python": 80,
            "Statistics": 25,
            "Linear Algebra": 15,
            "Machine Learning": 10,
            "Deep Learning": 5,
        }
    }
    submit_response = client.post("/api/assessment/submit", json=submit_payload, headers=headers)
    assert submit_response.status_code == 200

    result_response = client.get("/api/assessment/result", headers=headers)
    assert result_response.status_code == 200
    assert result_response.json()["scores"]["Python"] == 80

    gap_response = client.get("/api/skill-gap/analyze", headers=headers)
    assert gap_response.status_code == 200
    body = gap_response.json()
    assert body["target_role"] == "AI Engineer"
    assert "readiness_percent" in body
    assert len(body["skills"]) > 0
