import pytest

from fastapi.responses import JSONResponse

import asyncio
import json

from elysia.api.api_types import (
    GetObjectData,
    ViewPaginatedCollectionData,
    UserCollectionsData,
    CollectionMetadataData,
)
from elysia.api.dependencies.common import get_user_manager
from elysia.api.routes.collections import (
    collections,
    view_paginated_collection,
    collection_metadata,
    get_object,
)
from elysia.api.routes.init import initialise_user
from elysia.api.api_types import InitialiseUserData

from elysia.api.core.log import logger, set_log_level

set_log_level("CRITICAL")


def read_response(response: JSONResponse):
    return json.loads(response.body)


class TestEndpoints:

    @pytest.mark.asyncio
    async def test_collections(self):

        try:
            user_manager = get_user_manager()
            await initialise_user(
                InitialiseUserData(user_id="test_user", default_models=True),
                user_manager,
            )
            basic = await collections(
                UserCollectionsData(user_id="test_user"), user_manager
            )
            basic = read_response(basic)
            assert basic["error"] == ""
        finally:
            await user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_collection_metadata(self):
        try:
            user_manager = get_user_manager()
            await initialise_user(
                InitialiseUserData(user_id="test_user", default_models=True),
                user_manager,
            )
            basic = await collection_metadata(
                CollectionMetadataData(
                    user_id="test_user",
                    collection_name="example_verba_github_issues",
                ),
                user_manager,
            )
            basic = read_response(basic)
            assert basic["error"] == ""
        finally:
            await user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_get_object(self):
        try:
            user_manager = get_user_manager()
            await initialise_user(
                InitialiseUserData(user_id="test_user", default_models=True),
                user_manager,
            )

            # first manually get a UUID
            user_local = await user_manager.get_user_local("test_user")
            client_manager = user_local["client_manager"]
            async with client_manager.connect_to_async_client() as client:
                collection = client.collections.get("example_verba_github_issues")
                response = await collection.query.fetch_objects(limit=1)
                uuid = str(response.objects[0].uuid)

            # test with valid UUID
            basic = await get_object(
                GetObjectData(
                    user_id="test_user",
                    collection_name="example_verba_github_issues",
                    uuid=uuid,
                ),
                user_manager,
            )

            basic = read_response(basic)
            assert basic["error"] == ""

            # test with invalid UUID
            invalid = await get_object(
                GetObjectData(
                    user_id="test_user",
                    collection_name="example_verba_github_issues",
                    uuid="invalid",
                ),
                user_manager,
            )

            invalid = read_response(invalid)
            assert invalid["error"] != ""

        finally:
            await user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_view_paginated_collection(self):
        try:

            user_manager = get_user_manager()
            await initialise_user(
                InitialiseUserData(user_id="test_user", default_models=True),
                user_manager,
            )

            basic = await view_paginated_collection(
                ViewPaginatedCollectionData(
                    user_id="test_user",
                    collection_name="example_verba_github_issues",
                    page_size=50,
                    page_number=1,
                    sort_on="issue_created_at",
                    ascending=True,
                    filter_config={},
                ),
                user_manager,
            )
            basic = read_response(basic)
            assert basic["error"] == ""

            # test with filter
            filter = await view_paginated_collection(
                ViewPaginatedCollectionData(
                    user_id="test_user",
                    collection_name="example_verba_github_issues",
                    page_size=50,
                    page_number=1,
                    sort_on="issue_created_at",
                    ascending=True,
                    filter_config={
                        "type": "all",
                        "filters": [
                            {
                                "field": "issue_state",
                                "operator": "equal",
                                "value": "open",
                            }
                        ],
                    },
                ),
                user_manager,
            )
            filter = read_response(filter)
            assert filter["error"] == ""

            # test with out of bounds page number, should return empty list
            out_of_bounds = await view_paginated_collection(
                ViewPaginatedCollectionData(
                    user_id="test_user",
                    collection_name="example_verba_github_issues",
                    page_size=50,
                    page_number=100,
                    sort_on="issue_created_at",
                    ascending=True,
                    filter_config={
                        "type": "all",
                        "filters": [
                            {
                                "field": "issue_state",
                                "operator": "equal",
                                "value": "open",
                            }
                        ],
                    },
                ),
                user_manager,
            )
            out_of_bounds = read_response(out_of_bounds)
            assert out_of_bounds["error"] == ""
            assert len(out_of_bounds["items"]) == 0

        finally:
            await user_manager.close_all_clients()
