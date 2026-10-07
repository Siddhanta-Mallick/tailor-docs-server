from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app import database
from app.auth import require_user_id
from app.main import app


BASELINE = {
    "personal_info": {
        "name": "Avery Example",
        "phone": "555-0100",
        "email": {"url": "mailto:avery@example.com", "display": "avery@example.com"},
        "linkedin": {"url": "https://linkedin.com/in/avery", "display": "linkedin.com/in/avery"},
        "github": {"url": "https://github.com/avery", "display": "github.com/avery"},
    },
    "objective": "Backend engineer.",
    "education": [],
    "skills": [],
    "projects": [],
}
BASELINE_ID = UUID("b0e1e111-1111-4111-8111-111111111111")
SESSION_ID = UUID("5e551011-1111-4111-8111-111111111111")


@pytest.fixture(autouse=True)
def authenticated_request():
    app.dependency_overrides[require_user_id] = lambda: "cognito-user-id"
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_creates_named_baseline_only_on_explicit_request(client, monkeypatch):
    calls = []

    async def create(user_id, name, resume):
        calls.append((user_id, name, resume))
        return {"baseline_resume_id": BASELINE_ID, "name": name}

    monkeypatch.setattr(database, "create_baseline_resume", create)

    response = client.post("/api/baseline-resumes", json={"name": " Main resume ", "resume": BASELINE})

    assert response.status_code == 201
    assert response.json() == {"baseline_resume_id": str(BASELINE_ID), "name": "Main resume"}
    assert calls == [("cognito-user-id", "Main resume", BASELINE)]


def test_lists_only_baseline_ids_and_names(client, monkeypatch):
    async def list_for_user(user_id):
        assert user_id == "cognito-user-id"
        return [{"baseline_resume_id": BASELINE_ID, "name": "Main resume"}]

    monkeypatch.setattr(database, "list_baseline_resumes", list_for_user)

    response = client.get("/api/baseline-resumes")

    assert response.status_code == 200
    assert response.json() == [{"baseline_resume_id": str(BASELINE_ID), "name": "Main resume"}]


def test_session_save_uses_selected_owned_baseline(client, monkeypatch):
    async def create(user_id, name, description, baseline_id, current_resume):
        assert (user_id, name, description, baseline_id, current_resume) == (
            "cognito-user-id",
            "Platform role",
            "Build reliable APIs.",
            BASELINE_ID,
            BASELINE,
        )
        return {"session_id": SESSION_ID, "session_name": name}

    monkeypatch.setattr(database, "create_session", create)

    response = client.post(
        "/api/sessions",
        json={
            "session_name": "Platform role",
            "job_description": "Build reliable APIs.",
            "baseline_resume_id": str(BASELINE_ID),
            "current_resume": BASELINE,
        },
    )

    assert response.status_code == 201
    assert response.json() == {"session_id": str(SESSION_ID), "session_name": "Platform role"}


def test_session_retrieval_hides_other_users_sessions(client, monkeypatch):
    async def get_for_user(user_id, session_id):
        assert (user_id, session_id) == ("cognito-user-id", SESSION_ID)
        return None

    monkeypatch.setattr(database, "get_session", get_for_user)

    response = client.get(f"/api/sessions/{SESSION_ID}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found."}


def test_session_detail_loads_saved_current_resume_and_job_description(client, monkeypatch):
    async def get_for_user(user_id, session_id):
        return {
            "session_id": session_id,
            "session_name": "Platform role",
            "job_description": "Build reliable APIs.",
            "baseline_resume_id": BASELINE_ID,
            "baseline_jd_score": None,
            "current_jd_score": None,
            "current_resume": BASELINE,
        }

    monkeypatch.setattr(database, "get_session", get_for_user)

    response = client.get(f"/api/sessions/{SESSION_ID}")

    assert response.status_code == 200
    assert response.json()["job_description"] == "Build reliable APIs."
    assert response.json()["current_resume"] == BASELINE
    assert response.json()["baseline_resume_id"] == str(BASELINE_ID)


def test_update_session_only_writes_on_explicit_save(client, monkeypatch):
    async def update(user_id, session_id, name, description, baseline_id, current_resume):
        assert (user_id, session_id, name, description, baseline_id, current_resume) == (
            "cognito-user-id",
            SESSION_ID,
            "Updated role",
            "Build reliable APIs.",
            BASELINE_ID,
            BASELINE,
        )
        return {"session_id": session_id, "session_name": name}

    monkeypatch.setattr(database, "update_session", update)

    response = client.put(
        f"/api/sessions/{SESSION_ID}",
        json={
            "session_name": "Updated role",
            "job_description": "Build reliable APIs.",
            "baseline_resume_id": str(BASELINE_ID),
            "current_resume": BASELINE,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"session_id": str(SESSION_ID), "session_name": "Updated role"}
