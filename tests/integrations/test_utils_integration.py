import os
import pytest
import requests

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
UTILS_URL = f"{BASE_URL}/util"
INIT_URL = f"{BASE_URL}/init"

TEST_USER = "endpoint_utils_user"
TEST_CONVO = "endpoint_utils_convo"


@pytest.fixture(scope="module", autouse=True)
def ensure_user_and_tree():
    # Ensure the user and tree exist before running tests
    requests.post(f"{INIT_URL}/user/{TEST_USER}")
    requests.post(
        f"{INIT_URL}/tree/{TEST_USER}/{TEST_CONVO}", json={"low_memory": True}
    )


def test_ner():
    payload = {"text": "Hello, world! Paris is a city."}
    response = requests.post(f"{UTILS_URL}/ner", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["error"] == ""
    assert "entity_spans" in data
    assert "noun_spans" in data


def test_title():
    payload = {
        "user_id": TEST_USER,
        "conversation_id": TEST_CONVO,
        "text": "Hello, world!",
    }
    response = requests.post(f"{UTILS_URL}/title", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "title" in data


def test_follow_up_suggestions():
    payload = {"user_id": TEST_USER, "conversation_id": TEST_CONVO}
    response = requests.post(f"{UTILS_URL}/follow_up_suggestions", json=payload)
    assert response.status_code == 200 or response.status_code == 401
    data = response.json()
    assert "error" in data
    assert "suggestions" in data


def test_debug():
    payload = {"user_id": TEST_USER, "conversation_id": TEST_CONVO}
    response = requests.post(f"{UTILS_URL}/debug", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "base_lm" in data
    assert "complex_lm" in data or "error" in data


def test_ner_invalid_payload():
    # Missing text field
    response = requests.post(f"{UTILS_URL}/ner", json={})
    assert response.status_code in (400, 422)


def test_title_invalid_user():
    payload = {
        "user_id": "nonexistent_user",
        "conversation_id": "nonexistent_convo",
        "text": "Hello, world!",
    }
    response = requests.post(f"{UTILS_URL}/title", json=payload)
    # Should return 200 with error in payload, or 401 if conversation timed out
    assert response.status_code in (200, 401)
    data = response.json()
    assert "error" in data


def test_follow_up_suggestions_invalid_user():
    payload = {"user_id": "nonexistent_user", "conversation_id": "nonexistent_convo"}
    response = requests.post(f"{UTILS_URL}/follow_up_suggestions", json=payload)
    assert response.status_code in (200, 408)
    data = response.json()
    assert "error" in data


def test_debug_invalid_user():
    payload = {"user_id": "nonexistent_user", "conversation_id": "nonexistent_convo"}
    response = requests.post(f"{UTILS_URL}/debug", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "error" in data or "base_lm" in data
