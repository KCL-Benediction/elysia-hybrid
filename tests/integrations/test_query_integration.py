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

TEST_USER = "endpoint_query_user"
TEST_CONVO = "endpoint_query_convo"
TEST_QUERY_ID = "endpoint_query_query"


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
        f"{INIT_URL}/tree/{TEST_USER}/{TEST_CONVO}",
        json={"low_memory": True},
    )


def test_query_integration():
    # Simulate a query
    query_payload = {
        "user_id": TEST_USER,
        "conversation_id": TEST_CONVO,
        "query": "What is the capital of France?",
        "query_id": TEST_QUERY_ID,
        "collection_names": ["Example_verba_github_issues"],
        "route": "",
        "mimick": False,
    }

    results = []

    def on_message(ws, message):
        results.append(json.loads(message))

    ws = websocket.WebSocketApp(
        QUERY_URL,
        on_message=on_message,
    )
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.daemon = True
    ws_thread.start()
    time.sleep(1)

    # wait for query to complete
    ws.send(json.dumps(query_payload))
    while len(results) != 0 and results[-1]["type"] != "completed":
        time.sleep(0.1)

    for result in results:
        assert "type" in result
        assert "id" in result
        assert "user_id" in result and result["user_id"] == TEST_USER
        assert "conversation_id" in result and result["conversation_id"] == TEST_CONVO
        assert "query_id" in result and result["query_id"] == TEST_QUERY_ID
        assert "payload" in result

    # close the connection
    ws.close()
    ws_thread.join(timeout=1)
