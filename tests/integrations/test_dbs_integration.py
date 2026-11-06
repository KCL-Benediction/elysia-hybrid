import os
import random
import pytest
import requests
import json
import time
import threading
import websocket

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
INIT_URL = f"{BASE_URL}/init"
DB_URL = f"{BASE_URL}/db"
QUERY_URL = f"ws://localhost:8000/ws/query"

TEST_USER = "endpoint_db_user"
TEST_CONVO = "endpoint_db_convo"
TEST_QUERY_ID = "endpoint_db_query_id"


@pytest.fixture(scope="module", autouse=True)
def ensure_user_and_tree():
    # Ensure the user and tree exist before running tests
    requests.post(f"{INIT_URL}/user/{TEST_USER}")
    requests.post(
        f"{INIT_URL}/tree/{TEST_USER}/{TEST_CONVO}",
        json={"low_memory": True},
    )


@pytest.mark.asyncio
async def test_dbs_integration():

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
    while len(results) == 0 or (
        results[-1]["type"] != "completed"
        and results[-1]["type"] != "tree_timeout_error"
        and results[-1]["type"] != "user_timeout_error"
        and results[-1]["type"] != "error"
    ):
        time.sleep(0.1)

    # should have saved
    response = requests.get(f"{DB_URL}/{TEST_USER}/load_tree/{TEST_CONVO}")
    assert "rebuild" in response.json()
    assert "error" in response.json()
    assert response.json()["error"] == ""
    assert len(response.json()["rebuild"]) > 0

    # delete tree
    response = requests.delete(f"{DB_URL}/{TEST_USER}/delete_tree/{TEST_CONVO}")
    assert response.json()["error"] == ""
