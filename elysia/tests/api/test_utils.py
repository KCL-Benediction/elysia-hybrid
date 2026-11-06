import pytest
from elysia.tests.dummy_adapter import dummy_adapter

from fastapi.responses import JSONResponse

import json

from elysia.api.core.log import set_log_level
from elysia.api.dependencies.common import get_user_manager


set_log_level("CRITICAL")

from elysia.api.routes.init import initialise_tree
from elysia.api.routes.utils import (
    named_entity_recognition,
    title,
    follow_up_suggestions,
    debug,
)
from elysia.api.routes.init import initialise_user
from elysia.api.api_types import (
    NERData,
    TitleData,
    FollowUpSuggestionsData,
    DebugData,
    InitialiseTreeData,
    InitialiseUserData,
)


def read_response(response: JSONResponse):
    return json.loads(response.body)


class fake_websocket:
    results = []

    async def send_json(self, data: dict):
        self.results.append(data)


class TestUtils:

    @pytest.mark.asyncio
    async def test_ner(self):
        try:
            out = await named_entity_recognition(NERData(text="Hello, world!"))
            response = read_response(out)
            assert response["error"] == ""
        finally:
            await get_user_manager().close_all_clients()

    @pytest.mark.asyncio
    async def test_title(self):
        try:
            user_manager = get_user_manager()
            # local_user = user_manager.get_user_local(user_id="test_user")

            out = await initialise_user(
                InitialiseUserData(
                    user_id="test_user",
                    default_models=True,
                ),
                user_manager,
            )
            response = read_response(out)
            assert response["error"] == ""

            out = await initialise_tree(
                InitialiseTreeData(
                    user_id="test_user",
                    conversation_id="test_conversation",
                ),
                user_manager,
            )

            response = read_response(out)
            assert response["error"] == ""

            with dummy_adapter():
                out = await title(
                    TitleData(
                        user_id="test_user",
                        conversation_id="test_conversation",
                        text="Hello, world!",
                    ),
                    user_manager,
                )

            response = read_response(out)
            assert response["error"] == ""
        finally:
            await get_user_manager().close_all_clients()

    @pytest.mark.asyncio
    async def test_follow_up_suggestions(self):
        try:
            user_manager = get_user_manager()
            # local_user = awaituser_manager.get_user_local(user_id="test_user")

            out = await initialise_user(
                InitialiseUserData(
                    user_id="test_user",
                    default_models=True,
                ),
                user_manager,
            )
            response = read_response(out)
            assert response["error"] == ""

            out = await initialise_tree(
                InitialiseTreeData(
                    user_id="test_user",
                    conversation_id="test_conversation",
                ),
                user_manager,
            )
            response = read_response(out)
            assert response["error"] == ""

            with dummy_adapter():
                out = await follow_up_suggestions(
                    FollowUpSuggestionsData(
                        user_id="test_user",
                        conversation_id="test_conversation",
                    ),
                    user_manager,
                )
            response = read_response(out)
            assert response["error"] == ""
        finally:
            await get_user_manager().close_all_clients()

    def test_debug(self):
        # TODO: Implement this
        pass


if __name__ == "__main__":
    import asyncio

    asyncio.run(TestUtils().test_follow_up_suggestions())
