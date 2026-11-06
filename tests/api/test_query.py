import asyncio
import pytest
from fastapi.responses import JSONResponse

import json

from elysia.api.core.log import logger, set_log_level
from elysia.api.dependencies.common import get_user_manager

set_log_level("CRITICAL")

from elysia.api.routes.query import process
from elysia.api.api_types import QueryData, InitialiseTreeData

from elysia.api.routes.init import initialise_user, initialise_tree


def read_response(response: JSONResponse):
    return json.loads(response.body)


class fake_websocket:
    results = []

    async def send_json(self, data: dict):
        self.results.append(data)


async def initialise_user_and_tree(user_id: str, conversation_id: str):
    user_manager = get_user_manager()

    response = await initialise_user(
        user_id,
        user_manager,
    )

    response = await initialise_tree(
        user_id,
        conversation_id,
        InitialiseTreeData(
            low_memory=True,
        ),
        user_manager,
    )


async def delete_user_and_tree(user_id: str, conversation_id: str):
    user_manager = get_user_manager()
    await user_manager.delete_tree(user_id, conversation_id)


class TestQuery:

    @pytest.mark.asyncio
    async def test_query(self):

        try:

            user_id = "test_user"
            conversation_id = "test_conversation"
            query_id = "test_query"

            websocket = fake_websocket()

            await initialise_user_and_tree(user_id, conversation_id)

            try:
                out = await process(
                    QueryData(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        query="hi!",
                        query_id=query_id,
                        collection_names=["test_collection_1", "test_collection_2"],
                    ).model_dump(),
                    websocket,
                    get_user_manager(),
                )

                # check all payloads are valid
                for i, result in enumerate(websocket.results):
                    print(i, result["type"])
                    assert isinstance(result, dict)
                    assert "type" in result
                    assert "id" in result
                    assert "conversation_id" in result
                    assert "query_id" in result
                    assert "payload" in result
                    assert isinstance(result["payload"], dict)
                    if "objects" in result["payload"]:
                        for obj in result["payload"]["objects"]:
                            assert isinstance(obj, dict)
                    if "metadata" in result["payload"]:
                        assert isinstance(result["payload"]["metadata"], dict)
                    if "text" in result["payload"]:
                        assert isinstance(result["payload"]["text"], str)

                    if result["type"] == "ner":
                        assert isinstance(result["payload"]["text"], str)
                        assert isinstance(result["payload"]["entity_spans"], list)
                        assert isinstance(result["payload"]["noun_spans"], list)
                        assert isinstance(result["payload"]["error"], str)
                        assert result["payload"]["error"] == ""

                    if result["type"] == "title":
                        assert isinstance(result["payload"]["title"], str)
                        assert isinstance(result["payload"]["error"], str)
                        assert result["payload"]["error"] == ""

                    if result["type"] == "completed":
                        assert i == len(websocket.results) - 1
                        assert websocket.results[i - 1]["type"] == "title"

            finally:
                await delete_user_and_tree(user_id, conversation_id)

        finally:
            await get_user_manager().close_all_clients()
