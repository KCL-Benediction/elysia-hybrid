import pytest

from fastapi.responses import JSONResponse

import json
import os
import random
from elysia.api.api_types import ProcessCollectionData, SaveConfigUserData
from elysia.api.dependencies.common import get_user_manager
from elysia.api.routes.init import initialise_user
from elysia.api.routes.processor import process_collection
from elysia.util.client import ClientManager
from elysia.api.core.log import logger, set_log_level
from elysia.preprocess.collection import (
    delete_preprocessed_collection_async,
    preprocessed_collection_exists_async,
)
from elysia.api.routes.user_config import get_current_user_config, save_config_user

from weaviate.classes.config import Configure
from weaviate.classes.query import Filter


set_log_level("CRITICAL")

user_manager = get_user_manager()


def read_response(response: JSONResponse):
    return json.loads(response.body)


class fake_websocket:
    def __init__(self):
        self.results = []

    async def send_json(self, data: dict):
        self.results.append(data)


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


class TestProcessor:

    @pytest.mark.asyncio
    async def test_process_no_api_keys(self):

        user_id = "test_user_Process_no_api_keys"

        await initialise_user(
            user_id,
            user_manager,
        )
        local_user = await user_manager.get_user_local(user_id)
        client_manager = local_user["client_manager"]
        collection_name = create_collection(client_manager)

        try:
            # get config
            response = await get_current_user_config(user_id, user_manager)
            response = read_response(response)
            config_id = response["config"]["id"]
            config_name = response["config"]["name"]

            # remove api keys
            await save_config_user(
                user_id,
                config_id,
                SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={
                        "settings": {
                            "BASE_MODEL": "gemini-2.0-flash-001",
                            "BASE_PROVIDER": "openrouter/google",
                            "COMPLEX_MODEL": "gemini-2.0-flash-001",
                            "COMPLEX_PROVIDER": "openrouter/google",
                            "WCD_URL": os.getenv("WCD_URL"),
                            "WCD_API_KEY": os.getenv("WCD_API_KEY"),
                            "API_KEYS": {},
                        }
                    },
                    frontend_config={},
                ),
                user_manager,
            )

            websocket = fake_websocket()
            await process_collection(
                ProcessCollectionData(
                    user_id=user_id, collection_name=collection_name
                ).model_dump(),
                websocket,
                user_manager,
            )

            error_found = False
            for result in websocket.results:
                error_found = result["error"] != ""
            assert error_found

        finally:

            # delete the collections
            try:
                with client_manager.connect_to_client() as client:

                    if client.collections.exists(collection_name):
                        client.collections.delete(collection_name)

                    if await preprocessed_collection_exists_async(
                        collection_name, client_manager
                    ):
                        await delete_preprocessed_collection_async(
                            collection_name, client_manager
                        )

            except Exception as e:
                print(f"Can't delete collection: {str(e)}")
                pass

            await user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_process_collection(self):

        user_id = "test_user_Process_collection"
        try:
            await initialise_user(
                user_id,
                user_manager,
            )
            local_user = await user_manager.get_user_local(user_id)
            client_manager = local_user["client_manager"]

            collection_name = create_collection(client_manager)

            websocket = fake_websocket()
            await process_collection(
                ProcessCollectionData(
                    user_id=user_id, collection_name=collection_name
                ).model_dump(),
                websocket,
                user_manager,
            )
            for i, result in enumerate(websocket.results):
                if result["error"] != "":
                    print(result)
                    assert (
                        False
                    ), f"({i}) Message i-1: {websocket.results[i-1]['message']}, error: {result['error']}"

            for result in websocket.results[:-1]:
                assert result["type"] == "update"
                assert result["progress"] < 1

            assert websocket.results[-1]["type"] == "completed"
            assert websocket.results[-1]["progress"] == 1

            with client_manager.connect_to_client() as client:
                assert client.collections.exists(collection_name)
                assert client.collections.exists("ELYSIA_METADATA__")
                metadata_collection = client.collections.get("ELYSIA_METADATA__")
                metadata = metadata_collection.query.fetch_objects(
                    filters=Filter.by_property("name").equal(collection_name),
                    limit=1,
                )
                assert len(metadata.objects) >= 1

        finally:

            # delete the collections
            try:
                with client_manager.connect_to_client() as client:

                    if client.collections.exists(collection_name):
                        client.collections.delete(collection_name)

                    if await preprocessed_collection_exists_async(
                        collection_name, client_manager
                    ):
                        await delete_preprocessed_collection_async(
                            collection_name, client_manager
                        )

            except Exception as e:
                print(f"Can't delete collection: {str(e)}")
                pass

            await user_manager.close_all_clients()
