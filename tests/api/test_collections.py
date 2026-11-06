import pytest
import random
from fastapi.responses import JSONResponse

import asyncio
import json

from elysia.api.api_types import (
    ViewPaginatedCollectionData,
    UpdateCollectionMetadataData,
    MetadataNamedVectorData,
    MetadataFieldData,
    InitialiseTreeData,
)
from elysia.api.dependencies.common import get_user_manager
from elysia.api.routes.collections import (
    collections_list,
    view_paginated_collection,
    collection_metadata,
    get_object,
    mapping_types,
    update_metadata,
    delete_metadata,
)
from elysia.api.routes.init import initialise_user, initialise_tree
from elysia.api.core.log import logger, set_log_level
from elysia.preprocess.collection import preprocess_async
from elysia.util.client import ClientManager

set_log_level("CRITICAL")

from weaviate.classes.config import Configure


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
            low_memory=False,
        ),
        user_manager,
    )


def create_collection(
    client_manager: ClientManager, collection_name: str | None = None
):
    """
    Create a new collection for testing.
    """

    r = random.randint(0, 1000)
    if collection_name is None:
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


def read_response(response: JSONResponse):
    return json.loads(response.body)


class TestEndpoints:

    @pytest.mark.asyncio
    async def test_collections(self):

        user_id = "test_user_collections"
        conversation_id = "test_conversation_collections"

        try:
            user_manager = get_user_manager()
            await initialise_user_and_tree(user_id, conversation_id)
            basic = await collections_list(user_id, user_manager)
            basic = read_response(basic)
            assert basic["error"] == ""
        finally:
            await user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_collection_metadata(self):

        user_id = "test_user_collection_metadata"
        conversation_id = "test_conversation_collection_metadata"

        try:
            user_manager = get_user_manager()
            await initialise_user_and_tree(user_id, conversation_id)
            basic = await collection_metadata(
                user_id,
                collection_name="Products",
                user_manager=user_manager,
            )
            basic = read_response(basic)
            assert basic["error"] == ""
            assert "summary" in basic["metadata"]
            assert "fields" in basic["metadata"]
            assert "mappings" in basic["metadata"]
            assert "length" in basic["metadata"]
            assert "mappings" in basic["metadata"]
            assert "index_properties" in basic["metadata"]
            assert "named_vectors" in basic["metadata"]
            assert "vectorizer" in basic["metadata"]

            basic2 = await collection_metadata(
                user_id,
                collection_name="Ecommerce",
                user_manager=user_manager,
            )
            basic2 = read_response(basic2)
            assert basic2["error"] == ""
        finally:
            await user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_get_object(self):

        user_id = "test_user_get_object"
        conversation_id = "test_conversation_get_object"

        try:
            user_manager = get_user_manager()
            await initialise_user_and_tree(user_id, conversation_id)

            # first manually get a UUID
            user_local = await user_manager.get_user_local(user_id)
            client_manager = user_local["client_manager"]
            async with client_manager.connect_to_async_client() as client:
                collection = client.collections.get("example_verba_github_issues")
                response = await collection.query.fetch_objects(limit=1)
                uuid = str(response.objects[0].uuid)

            # test with valid UUID
            basic = await get_object(
                user_id,
                collection_name="example_verba_github_issues",
                uuid=uuid,
                user_manager=user_manager,
            )

            basic = read_response(basic)
            assert basic["error"] == ""

            # test with invalid UUID
            invalid = await get_object(
                user_id,
                collection_name="example_verba_github_issues",
                uuid="invalid",
                user_manager=user_manager,
            )

            invalid = read_response(invalid)
            assert invalid["error"] != ""

        finally:
            await user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_view_paginated_collection(self):

        user_id = "test_user_view_paginated_collection"
        conversation_id = "test_conversation_view_paginated_collection"

        try:
            user_manager = get_user_manager()
            await initialise_user_and_tree(user_id, conversation_id)

            basic = await view_paginated_collection(
                user_id,
                collection_name="example_verba_github_issues",
                data=ViewPaginatedCollectionData(
                    query="",
                    page_size=50,
                    page_number=1,
                    sort_on="issue_created_at",
                    ascending=True,
                    filter_config={},
                ),
                user_manager=user_manager,
            )
            basic = read_response(basic)
            assert basic["error"] == ""

            # test with filter
            filter = await view_paginated_collection(
                user_id,
                collection_name="example_verba_github_issues",
                data=ViewPaginatedCollectionData(
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
                user_manager=user_manager,
            )
            filter = read_response(filter)
            assert filter["error"] == ""

            # test with query
            query = await view_paginated_collection(
                user_id,
                collection_name="example_verba_github_issues",
                data=ViewPaginatedCollectionData(
                    query="hello",
                    page_size=50,
                    page_number=1,
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
                user_manager=user_manager,
            )
            query = read_response(query)
            assert query["error"] == ""

            # test with out of bounds page number, should return empty list
            out_of_bounds = await view_paginated_collection(
                user_id,
                collection_name="example_verba_github_issues",
                data=ViewPaginatedCollectionData(
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
                user_manager=user_manager,
            )
            out_of_bounds = read_response(out_of_bounds)
            assert out_of_bounds["error"] == ""
            assert len(out_of_bounds["items"]) == 0

        finally:
            await user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_mapping_types(self):
        await mapping_types()

    @pytest.mark.asyncio
    async def test_update_metadata(self):

        user_id = "test_user_update_metadata"
        conversation_id = "test_conversation_update_metadata"

        try:
            user_manager = get_user_manager()
            await initialise_user_and_tree(user_id, conversation_id)

            # retrieve the metadata
            metadata = await collection_metadata(
                user_id=user_id,
                collection_name="Example_verba_github_issues",
                user_manager=user_manager,
            )
            metadata = read_response(metadata)
            assert metadata["error"] == ""
            metadata = metadata["metadata"]

            # record values
            old_named_vectors = metadata["named_vectors"]
            old_summary = metadata["summary"]
            old_mappings = metadata["mappings"]
            old_fields = metadata["fields"]

            # what to update
            new_named_vectors = [
                MetadataNamedVectorData(
                    name="issue_content",
                    enabled=True,
                    description="Directly related to the issue content.",
                )
            ]

            new_summary = "This is a test summary."
            new_mappings = {
                "product": {
                    "name": "issue_title",
                    "category": "issue_state",
                    "description": "issue_content",
                }
            }
            new_fields = [
                MetadataFieldData(
                    name="issue_title",
                    description="A test description for issue title.",
                )
            ]

            # update the metadata
            update_metadata_response = await update_metadata(
                user_id=user_id,
                collection_name="example_verba_github_issues",
                data=UpdateCollectionMetadataData(
                    named_vectors=new_named_vectors,
                    summary=new_summary,
                    mappings=new_mappings,
                    fields=new_fields,
                ),
                user_manager=user_manager,
            )
            update_metadata_response = read_response(update_metadata_response)
            assert update_metadata_response["error"] == ""

            # retrieve the metadata again
            metadata = await collection_metadata(
                user_id=user_id,
                collection_name="example_verba_github_issues",
                user_manager=user_manager,
            )
            metadata = read_response(metadata)
            assert metadata["error"] == ""
            metadata = metadata["metadata"]

            # check the values have been updated
            for named_vector in metadata["named_vectors"]:
                if named_vector["name"] == "issue_content":
                    assert named_vector["enabled"] == True
                    assert (
                        named_vector["description"]
                        == "Directly related to the issue content."
                    )
                    break

            assert metadata["summary"] == new_summary
            assert "product" in metadata["mappings"]
            for field in metadata["fields"]:
                if field["name"] == "issue_title":
                    assert field["description"] == new_fields[0].description
                    break

            # save current values
            midway_named_vectors = metadata["named_vectors"]
            midway_summary = metadata["summary"]
            midway_mappings = metadata["mappings"]
            midway_fields = metadata["fields"]

            # only update a portion of the metadata
            new_fields2 = [
                MetadataFieldData(
                    name="issue_updated_at",
                    description="A test description for issue title.",
                ),
                MetadataFieldData(
                    name="issue_created_at",
                    description="A test description for issue created at.",
                ),
            ]

            # update the metadata
            update_metadata2_response = await update_metadata(
                user_id=user_id,
                collection_name="example_verba_github_issues",
                data=UpdateCollectionMetadataData(
                    fields=new_fields2,
                ),
                user_manager=user_manager,
            )
            update_metadata2_response = read_response(update_metadata2_response)
            assert update_metadata2_response["error"] == ""

            # retrieve the metadata again
            metadata = await collection_metadata(
                user_id=user_id,
                collection_name="example_verba_github_issues",
                user_manager=user_manager,
            )
            metadata = read_response(metadata)
            assert metadata["error"] == ""
            metadata = metadata["metadata"]

            # check the values have been updated
            for field in metadata["fields"]:
                if field["name"] == "issue_updated_at":
                    assert field["description"] == new_fields2[0].description
                if field["name"] == "issue_created_at":
                    assert field["description"] == new_fields2[1].description

            # check that the other values are unchanged
            assert metadata["named_vectors"] == midway_named_vectors
            assert metadata["summary"] == midway_summary
            assert metadata["mappings"] == midway_mappings

            old_named_vectors_data = [
                MetadataNamedVectorData(
                    name=field["name"],
                    enabled=field["enabled"],
                    description=field["description"],
                )
                for field in old_named_vectors
            ]
            old_fields_data = [
                MetadataFieldData(
                    name=field["name"],
                    description=field["description"],
                )
                for field in old_fields
            ]
            old_mappings_data = old_mappings

            # change back to the original values
            update_metadata3_response = await update_metadata(
                user_id=user_id,
                collection_name="example_verba_github_issues",
                data=UpdateCollectionMetadataData(
                    named_vectors=old_named_vectors_data,
                    summary=old_summary,
                    mappings=old_mappings_data,
                    fields=old_fields_data,
                ),
                user_manager=user_manager,
            )
            update_metadata3_response = read_response(update_metadata3_response)
            assert update_metadata3_response["error"] == ""

        except Exception as e:
            from rich import print

            print(
                "\n\n[bold red]AN ERROR OCCURED DURING TESTING test_update_metadata[/bold red]\n"
                "This means that the example_verba_github_issues collection has been left in an unknown state.\n"
                "The metadata was being edited in this test, but the test did not finish successfully and it was not reset.\n"
                "The collection needs reprocessing to return to a working state.\n"
            )
            raise e
        finally:
            await user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_delete_metadata(self):
        user_id = "test_user_delete_metadata"
        conversation_id = "test_conversation_delete_metadata"
        collection_name = "test_collection_delete_metadata"

        user_manager = get_user_manager()
        await initialise_user_and_tree(user_id, conversation_id)

        user_local = await user_manager.get_user_local(user_id)
        client_manager = user_local["client_manager"]
        settings = user_local["tree_manager"].settings

        try:
            # create a collection
            collection_name = create_collection(client_manager, collection_name)

            # preprocess the collection
            async for _ in preprocess_async(
                collection_name=collection_name,
                client_manager=client_manager,
                force=False,
                settings=settings,
            ):
                pass

            # check the metadata has been created
            metadata = await collection_metadata(
                user_id=user_id,
                collection_name=collection_name,
                user_manager=user_manager,
            )
            metadata = read_response(metadata)
            assert metadata["error"] == ""
            assert metadata["metadata"] is not {} and metadata["metadata"] is not None

            # delete the metadata
            delete_metadata_response = await delete_metadata(
                user_id=user_id,
                collection_name=collection_name,
                user_manager=user_manager,
            )
            delete_metadata_response = read_response(delete_metadata_response)
            assert delete_metadata_response["error"] == ""

            # check that the metadata has been deleted
            metadata = await collection_metadata(
                user_id=user_id,
                collection_name=collection_name,
                user_manager=user_manager,
            )
            metadata = read_response(metadata)
            assert metadata["error"] != ""

        finally:
            await user_manager.close_all_clients()

            try:
                with client_manager.connect_to_client() as client:
                    client.collections.delete(collection_name)
            except Exception as e:
                pass
