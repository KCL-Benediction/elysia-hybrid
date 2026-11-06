import pytest
from fastapi.responses import JSONResponse

import json

from elysia.api.core.log import set_log_level
from elysia.api.dependencies.common import get_user_manager

set_log_level("CRITICAL")

from elysia.api.routes.init import initialise_tree, initialise_user
from elysia.api.api_types import InitialiseTreeData, InitialiseUserData


def read_response(response: JSONResponse):
    return json.loads(response.body)


class TestTree:

    @pytest.mark.asyncio
    async def test_tree(self):

        try:
            user_manager = get_user_manager()
            user_id = "test_user"
            conversation_id = "test_conversation"

            out = await initialise_user(
                InitialiseUserData(
                    user_id=user_id,
                    default_models=True,
                ),
                user_manager,
            )
            response = read_response(out)
            assert response["error"] == ""

            out = await initialise_tree(
                InitialiseTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    low_memory=True,
                ),
                user_manager,
            )

            response = read_response(out)
            assert response["error"] == ""

            out = await initialise_tree(
                InitialiseTreeData(
                    user_id=user_id + "2",
                    conversation_id=conversation_id + "2",
                    low_memory=True,
                ),
                user_manager,
            )

            response = read_response(out)
            assert response["error"] == ""
        finally:
            await get_user_manager().close_all_clients()
