import json

from fastapi.testclient import TestClient

from app.main import app
from app.models.resume import Resume


client = TestClient(app)

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


def test_returns_only_tailored_resume(monkeypatch):
    async def complete(**kwargs):
        from types import SimpleNamespace

        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(BASELINE)))])

    monkeypatch.setattr("app.services.tailorer.acompletion", complete)

    response = client.post(
        "/api/tailor/resume",
        json={"approved_job_description": "Build reliable APIs.", "baseline_resume": BASELINE},
    )

    assert response.status_code == 200
    assert response.json() == BASELINE


def test_rejects_missing_or_whitespace_job_description():
    for description in (None, "  \n"):
        response = client.post(
            "/api/tailor/resume",
            json={"approved_job_description": description, "baseline_resume": BASELINE},
        )
        assert response.status_code == 422


def test_invalid_baseline_is_rejected_before_generation(monkeypatch):
    async def complete(**kwargs):
        raise AssertionError("LiteLLM must not be called")

    monkeypatch.setattr("app.services.tailorer.acompletion", complete)
    invalid = {**BASELINE, "unknown": "field"}

    response = client.post(
        "/api/tailor/resume",
        json={"approved_job_description": "Build reliable APIs.", "baseline_resume": invalid},
    )

    assert response.status_code == 422


def test_invalid_generated_resume_returns_safe_502(monkeypatch):
    async def complete(**kwargs):
        from types import SimpleNamespace

        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"unknown": "secret"}'))])

    monkeypatch.setattr("app.services.tailorer.acompletion", complete)

    response = client.post(
        "/api/tailor/resume",
        json={"approved_job_description": "Build reliable APIs.", "baseline_resume": BASELINE},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Resume generation returned an invalid structure."}
    assert "secret" not in response.text


def test_rejects_unknown_generated_fields():
    assert Resume.model_validate(BASELINE).model_dump() == BASELINE
