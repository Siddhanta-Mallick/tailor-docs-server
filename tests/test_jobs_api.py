import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def assert_url_candidate(response):
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "url"
    assert body["requires_user_approval"] is True
    assert len(body["candidate_job_description"]) >= 50


def test_scrapes_fake_jobs_page():
    response = client.post(
        "/api/jobs/description/preview",
        json={"url": "https://realpython.github.io/fake-jobs/jobs/senior-python-developer-0.html"},
    )

    assert_url_candidate(response)
    assert "Senior Python Developer" in response.json()["candidate_job_description"]


def test_ajax_page_returns_unapproved_generic_content():
    response = client.post(
        "/api/jobs/description/preview",
        json={"url": "https://www.scrapethissite.com/pages/ajax-javascript/"},
    )

    assert_url_candidate(response)


@pytest.mark.parametrize("status", [403, 429])
def test_blocked_status_returns_manual_paste_error(status):
    response = client.post(
        "/api/jobs/description/preview",
        json={"url": f"https://httpbin.org/status/{status}"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "SCRAPE_BLOCKED_OR_FAILED",
        "message": "Could not retrieve usable job-description text. Please paste it manually.",
    }


@pytest.mark.parametrize("payload", [{}, {"url": "https://example.com", "text": "text"}])
def test_requires_exactly_one_source(payload):
    response = client.post("/api/jobs/description/preview", json=payload)

    assert response.status_code == 400
    assert response.json() == {"detail": "Provide exactly one of url or text."}


def test_returns_manual_text_as_unapproved_candidate():
    text = "x" * 15_001

    response = client.post("/api/jobs/description/preview", json={"text": text})

    assert response.status_code == 200
    assert response.json() == {
        "candidate_job_description": text[:15_000],
        "source": "text",
        "requires_user_approval": True,
    }


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        ({"text": "  \n"}, "Text must not be empty."),
        ({"url": "ftp://example.com"}, "URL must use http or https."),
        ({"url": "http://127.0.0.1"}, "URL host is not allowed."),
    ],
)
def test_rejects_invalid_sources(payload, detail):
    response = client.post("/api/jobs/description/preview", json=payload)

    assert response.status_code == 400
    assert response.json() == {"detail": detail}
