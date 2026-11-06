import os
import pytest
import requests
from datetime import datetime
import time
import json
import websocket
import threading

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
INIT_URL = f"{BASE_URL}/init"
QUERY_URL = f"ws://localhost:8000/ws/query"
FEEDBACK_URL = f"{BASE_URL}/feedback"

TEST_USER = "endpoint_feedback_user"
TEST_CONVO = "endpoint_feedback_convo"
TEST_QUERY_ID = "endpoint_feedback_query"


def on_open(ws):
    print("Opened connection")


def on_message(ws, message):
    print("Received message:", message)


def on_error(ws, error):
    print("Error:", error)


def on_close(ws):
    print("Closed connection")


@pytest.fixture(scope="module", autouse=True)
def ensure_user_and_tree():
    # Ensure the user and tree exist before running tests
    requests.post(f"{INIT_URL}/user/{TEST_USER}")
    requests.post(
        f"{INIT_URL}/tree/{TEST_USER}/{TEST_CONVO}", json={"low_memory": True}
    )


def test_feedback_metadata_initial():
    response = requests.get(f"{FEEDBACK_URL}/metadata/{TEST_USER}")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["error"] == ""
    assert "total_feedback" in data
    assert "feedback_by_value" in data
    assert "feedback_by_date" in data


def test_add_and_remove_feedback_cycle():
    # Simulate a query
    query_payload = {
        "user_id": TEST_USER,
        "conversation_id": TEST_CONVO,
        "query": "Hello, world!",
        "query_id": TEST_QUERY_ID,
        "collection_names": ["Example_verba_github_issues"],
        "route": "",
        "mimick": False,
    }
    # Allow some time for processing
    ws = websocket.WebSocketApp(
        QUERY_URL,
        on_error=on_error,
    )
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.daemon = True
    ws_thread.start()
    time.sleep(1)

    ws.send(json.dumps(query_payload))
    time.sleep(15)
    ws.close()
    ws_thread.join(timeout=1)

    # Get initial feedback metadata
    response = requests.get(f"{FEEDBACK_URL}/metadata/{TEST_USER}")
    assert response.status_code == 200
    data = response.json()
    assert data["error"] == ""

    # Add feedback
    add_payload = {
        "user_id": TEST_USER,
        "conversation_id": TEST_CONVO,
        "query_id": TEST_QUERY_ID,
        "feedback": 1,
    }
    response = requests.post(f"{FEEDBACK_URL}/add", json=add_payload)
    assert response.status_code == 200
    assert response.json()["error"] == ""

    # Check feedback metadata again
    response = requests.get(f"{FEEDBACK_URL}/metadata/{TEST_USER}")
    assert response.status_code == 200
    data = response.json()
    assert data["error"] == ""

    # Remove feedback
    remove_payload = {
        "user_id": TEST_USER,
        "conversation_id": TEST_CONVO,
        "query_id": TEST_QUERY_ID,
    }
    response = requests.post(f"{FEEDBACK_URL}/remove", json=remove_payload)
    assert response.status_code == 200
    assert response.json()["error"] == ""


def test_add_feedback_invalid_user():
    payload = {
        "user_id": "nonexistent_user",
        "conversation_id": "nonexistent_convo",
        "query_id": "nonexistent_query",
        "feedback": 1,
    }
    response = requests.post(f"{FEEDBACK_URL}/add", json=payload)
    assert response.status_code == 500 or response.json()["error"] != ""


def test_remove_feedback_invalid_user():
    payload = {
        "user_id": "nonexistent_user",
        "conversation_id": "nonexistent_convo",
        "query_id": "nonexistent_query",
    }
    response = requests.post(f"{FEEDBACK_URL}/remove", json=payload)
    assert response.status_code == 500 or response.json()["error"] != ""


def test_feedback_metadata_invalid_user():
    response = requests.get(f"{FEEDBACK_URL}/metadata/nonexistent_user")
    assert response.status_code == 500 or response.json()["error"] != ""
