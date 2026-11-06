import asyncio
import pytest
from fastapi.responses import JSONResponse

import json

from elysia.api.core.log import logger, set_log_level
from elysia.api.dependencies.common import get_user_manager

set_log_level("CRITICAL")

from elysia.api.routes.query import process
from elysia.api.api_types import QueryData, InitialiseUserData, InitialiseTreeData
from elysia.tests.dummy_adapter import dummy_adapter
from elysia.api.routes.init import initialise_user, initialise_tree


def read_response(response: JSONResponse):
    return json.loads(response.body)


class fake_websocket:
    results = []

    async def send_json(self, data: dict):
        self.results.append(data)


class TestQuery:

    @pytest.mark.asyncio
    async def test_query(self):

        with dummy_adapter():
            try:

                user_id = "test_user"
                conversation_id = "test_conversation"
                query_id = "test_query"

                websocket = fake_websocket()

                await initialise_user(
                    InitialiseUserData(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        default_models=True,
                    )
                )

                await initialise_tree(
                    InitialiseTreeData(
                        user_id=user_id,
                        conversation_id=conversation_id,
                    )
                )

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
                for result in websocket.results:
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
            finally:
                await get_user_manager().close_all_clients()


if __name__ == "__main__":
    asyncio.run(TestQuery().test_query())
