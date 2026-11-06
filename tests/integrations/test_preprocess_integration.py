import os
import pytest
import requests
from datetime import datetime
import time
import json
import websocket
import threading
import random
from weaviate.classes.config import Configure
from elysia.util.client import ClientManager


BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
INIT_URL = f"{BASE_URL}/init"
PREPROCESS_URL = f"ws://localhost:8000/ws/process_collection"

TEST_USER = "endpoint_preprocess_user"
TEST_CONVO = "endpoint_preprocess_convo"
TEST_QUERY_ID = "endpoint_preprocess_query"


def create_collection(client_manager: ClientManager):
    """
    Create a new collection for testing.
    """

    r = random.randint(0, 1000)
    collection_name = f"test_elysia_collection_{r}"

    # create the collection
    vectorizer = Configure.Vectorizer.text2vec_openai(model="text-embedding-3-small")

    with client_manager.connect_to_client() as client:
        client.collections.create(
            collection_name,
            vectorizer_config=vectorizer,
        )

    lorem_ipsum = [
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
        "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.",
        "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
    ]

    # upload some random data
    with client_manager.connect_to_client() as client:
        collection = client.collections.get(collection_name)
        for i in range(4):
            collection.data.insert(
                {"name": f"test_object_{i}", "description": lorem_ipsum[i]}
            )

    return collection_name


@pytest.fixture(scope="module", autouse=True)
def ensure_user_and_tree():
    # Ensure the user and tree exist before running tests
    requests.post(f"{INIT_URL}/user/{TEST_USER}")
    requests.post(
        f"{INIT_URL}/tree/{TEST_USER}/{TEST_CONVO}",
        json={"low_memory": True},
    )


@pytest.mark.asyncio
async def test_preprocess_integration():

    try:
        # create a collection
        client_manager = ClientManager()
        collection_name = create_collection(client_manager)

        # preprocess the collection
        payload = {
            "user_id": TEST_USER,
            "collection_name": collection_name,
        }
        results = []

        def on_message(ws, message):
            results.append(json.loads(message))

        ws = websocket.WebSocketApp(
            PREPROCESS_URL,
            on_message=on_message,
        )
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        time.sleep(1)

        # wait for query to complete
        ws.send(json.dumps(payload))
        while len(results) == 0 or results[-1]["type"] != "completed":
            time.sleep(0.1)

        for result in results:
            assert "type" in result
            if result["type"] == "update":
                assert "progress" in result
                assert result["progress"] < 1
            elif result["type"] == "completed":
                assert "progress" in result
                assert result["progress"] == 1

        # check that the collection has been preprocessed
        with client_manager.connect_to_client() as client:
            assert client.collections.exists(
                f"ELYSIA_METADATA_{collection_name.lower()}__"
            )

    finally:

        # delete the collections
        try:
            with client_manager.connect_to_client() as client:

                if client.collections.exists(collection_name):
                    client.collections.delete(collection_name)

                if client.collections.exists(
                    f"ELYSIA_METADATA_{collection_name.lower()}"
                ):
                    client.collections.delete(
                        f"ELYSIA_METADATA_{collection_name.lower()}"
                    )
        except Exception as e:
            print(f"Can't delete collection: {str(e)}")
            pass

        await client_manager.close_clients()
