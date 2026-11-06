import asyncio
import os
import pytest
from typing import Any
from weaviate.classes.query import Filter, QueryReference

from elysia.tree.objects import Environment
from elysia.objects import (
    Completed,
    Response,
    Status,
    Text,
    Update,
    Warning,
    Result,
)
from elysia.tools.retrieval.chunk import AsyncCollectionChunker
from elysia.tools.retrieval.objects import (
    ConversationRetrieval,
    DocumentRetrieval,
    MessageRetrieval,
)
from elysia.util.client import ClientManager
from elysia.util.parsing import format_dict_to_serialisable


class TestObjects:

    async def start_client_manager(self):
        client_manager = ClientManager(
            wcd_url=os.getenv("WCD_URL"),
            wcd_api_key=os.getenv("WCD_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )
        await client_manager.start_clients()
        return client_manager

    async def do_basic_result(self, object_type: Any, object_name: str):
        result = object_type(
            objects=[{"a": 1, "b": 2, "c": 3}],
            metadata={"metadata_a": 1, "metadata_b": 2, "metadata_c": 3},
        )
        result_json = result.to_json()

        assert result_json == [{"a": 1, "b": 2, "c": 3}], "Objects should be equal"

        frontend_result = await result.to_frontend(
            "user_id", "conversation_id", "query_id"
        )

        # all id vars should be present
        for key in ["user_id", "conversation_id", "query_id"]:
            assert key in frontend_result, f"'{key}' not found in the frontend result"

        # type and payload type should be correct
        assert frontend_result["type"] == "result"
        assert frontend_result["payload"]["type"] == object_name

        # objects should be correct (but there can be more objects in frontend result)
        for i, obj in enumerate(result_json):
            for key in obj:
                assert (
                    key in frontend_result["payload"]["objects"][i]
                ), f"'{key}' not found in the frontend result"

        # metadata should be the same
        assert frontend_result["payload"]["metadata"] == result.metadata

    async def do_result_with_mapping(
        self,
        object_type: Any,
        objects: list[dict],
        mapping: dict,
        unmapped_keys: list[str] = [],
    ):
        result = object_type(
            objects=objects, metadata={}, mapping=mapping, unmapped_keys=unmapped_keys
        )
        result_json = result.to_json(True)

        for i, obj in enumerate(objects):
            for mapping_key in mapping:
                assert mapping_key in result_json[i]

            for obj_key in obj:
                if obj_key not in unmapped_keys:
                    assert obj_key not in result_json[i]

            for unmapped_key in unmapped_keys:
                assert unmapped_key in result_json[i]

        frontend_result = await result.to_frontend(
            "user_id", "conversation_id", "query_id"
        )

        for i, obj in enumerate(objects):
            for mapping_key in mapping:
                assert mapping_key in frontend_result["payload"]["objects"][i]

    async def do_update(self, object_type: Any, object_name: str):
        result = object_type(
            "this is a test",
        )
        frontend_result = await result.to_frontend(
            "user_id", "conversation_id", "query_id"
        )
        assert frontend_result["type"] == object_name
        assert isinstance(frontend_result["payload"], dict)

    @pytest.mark.asyncio
    async def test_updates(self):
        types = [
            Status,
            Warning,
        ]
        names = [
            "status",
            "warning",
            "error",
        ]
        for object_type, object_name in zip(types, names):
            await self.do_update(object_type, object_name)

    async def _retrieve_unchunked_documents(
        self, collection_name: str, client_manager: ClientManager
    ):
        async with client_manager.connect_to_async_client() as client:
            collection = client.collections.get(collection_name)
            documents = await collection.query.fetch_objects(
                limit=2,
                return_references=QueryReference(link_on="isChunked"),
            )
        return documents

    async def _retrieve_chunked_documents(
        self, collection_name: str, client_manager: ClientManager
    ):
        async with client_manager.connect_to_async_client() as client:
            collection = client.collections.get(collection_name)
            documents = await collection.query.fetch_objects(
                limit=2,
                return_references=QueryReference(link_on="fullDocument"),
            )
        return documents

    async def _create_chunked_reference(
        self, collection_name: str, client_manager: ClientManager
    ):
        collection_chunker = AsyncCollectionChunker(collection_name)
        await collection_chunker.create_chunked_reference("content", client_manager)

    async def _chunk_documents(
        self, collection_name: str, response, client_manager: ClientManager
    ):
        collection_chunker = AsyncCollectionChunker(collection_name)
        await collection_chunker(response, "content", client_manager)

    async def get_collection_information(
        self, collection_name: str, client_manager: ClientManager
    ):
        async with client_manager.connect_to_async_client() as client:
            metadata_name = "ELYSIA_METADATA__"
            metadata_collection = client.collections.get(metadata_name)
            metadata = await metadata_collection.query.fetch_objects(
                filters=Filter.by_property("name").equal(collection_name),
                limit=1,
            )
            properties = metadata.objects[0].properties
            format_dict_to_serialisable(properties)
            return properties

    async def get_document_retrievals(self):
        collection_name = "ml_wikipedia"
        client_manager = await self.start_client_manager()

        # get the collection information
        collection_information = await self.get_collection_information(
            collection_name, client_manager
        )
        await self._create_chunked_reference(collection_name, client_manager)

        # retrieve some documents
        unchunked_documents = await self._retrieve_unchunked_documents(
            collection_name, client_manager
        )

        # chunk the documents
        await self._chunk_documents(
            collection_name, unchunked_documents, client_manager
        )

        # retrieve the chunked documents
        chunked_documents = await self._retrieve_chunked_documents(
            f"ELYSIA_CHUNKED_{collection_name.lower()}__", client_manager
        )

        unchunked_document_properties = [
            doc.properties for doc in unchunked_documents.objects
        ]
        chunked_document_properties = [
            doc.properties for doc in chunked_documents.objects
        ]

        for i, prop in enumerate(unchunked_document_properties):
            prop["uuid"] = str(unchunked_documents.objects[i].uuid)

        for i, prop in enumerate(chunked_document_properties):
            prop["uuid"] = str(chunked_documents.objects[i].uuid)

        # create a retrieval object
        non_chunked_retrieval = DocumentRetrieval(
            objects=unchunked_document_properties,
            metadata={"collection_name": "ml_wikipedia", "chunked": False},
            mapping=collection_information["mappings"]["document"],
        )
        chunked_retrieval = DocumentRetrieval(
            objects=chunked_document_properties,
            metadata={"collection_name": "ml_wikipedia", "chunked": True},
            mapping=collection_information["mappings"]["document"],
        )
        await chunked_retrieval.async_init(client_manager)
        await client_manager.close_clients()

        return non_chunked_retrieval, chunked_retrieval

    @pytest.mark.asyncio
    async def test_document_retrieval(self):
        non_chunked_retrieval, chunked_retrieval = await self.get_document_retrievals()

        chunked_json = chunked_retrieval.to_json(mapping=False)

        chunked_fe = await chunked_retrieval.to_frontend(
            "user_id", "conversation_id", "query_id"
        )

        # Check that the document attached to the chunk is >= length of the chunk
        for i, full_doc_obj in enumerate(chunked_fe["payload"]["objects"]):
            assert len(full_doc_obj["content"]) >= len(chunked_json[i]["content"])

        # Check that all chunk spans from the chunk exist in the full documnet
        all_chunk_spans = [
            (obj["uuid"], obj["chunk_spans"])
            for obj in chunked_json
            if obj["chunk_spans"] != []
        ]

        # Find all unique instances of chunkID+chunkSpan
        which_chunk_spans_exist = {
            str(all_chunk_spans[i][0]) + str(all_chunk_spans[i][1]): False
            for i in range(len(all_chunk_spans))
        }

        # Look through full documents (FE payload-objects) and check if the chunk content is present
        for i, full_doc_obj in enumerate(chunked_fe["payload"]["objects"]):
            for chunk_span in full_doc_obj["chunk_spans"]:
                ind = str(chunk_span["uuid"]) + str(
                    [chunk_span["start"], chunk_span["end"]]
                )
                if ind in which_chunk_spans_exist:
                    which_chunk_spans_exist[ind] = True

        assert all(which_chunk_spans_exist.values())

    def test_environment(self):
        environment = Environment()

        assert environment.is_empty()

        res = Result(
            objects=[{"a": 1, "b": 2}],
            metadata={"metadata_a": "hello", "metadata_b": 10},
            name="test_result",
        )
        environment.add("test_tool", res)

        assert not environment.is_empty()
        assert (
            environment.environment["test_tool"]["test_result"][0]["objects"][0]["a"]
            == 1
        )
        assert (
            environment.environment["test_tool"]["test_result"][0]["objects"][0]["b"]
            == 2
        )

        assert environment.environment["test_tool"]["test_result"][0]["metadata"] == {
            "metadata_a": "hello",
            "metadata_b": 10,
        }

        found_item = environment.find("test_tool", "test_result")
        assert found_item[0]["objects"][0]["a"] == 1
        assert found_item[0]["objects"][0]["b"] == 2
        assert found_item[0]["metadata"] == {
            "metadata_a": "hello",
            "metadata_b": 10,
        }

        found_item_index = environment.find("test_tool", "test_result", 0)
        assert found_item_index["objects"][0]["a"] == 1
        assert found_item_index["objects"][0]["b"] == 2
        assert found_item_index["metadata"] == {
            "metadata_a": "hello",
            "metadata_b": 10,
        }

        environment.replace("test_tool", "test_result", [{"c": 3, "d": 4}])
        assert (
            environment.environment["test_tool"]["test_result"][0]["objects"][0]["c"]
            == 3
        )
        assert (
            environment.environment["test_tool"]["test_result"][0]["objects"][0]["d"]
            == 4
        )

        environment.replace(
            "test_tool", "test_result", [{"e": 5, "f": "hello"}], index=0
        )
        assert (
            environment.environment["test_tool"]["test_result"][0]["objects"][0]["e"]
            == 5
        )
        assert (
            environment.environment["test_tool"]["test_result"][0]["objects"][0]["f"]
            == "hello"
        )

        json_obj = environment.environment
        assert "test_tool" in json_obj
        assert "test_result" in json_obj["test_tool"]
        assert json_obj["test_tool"]["test_result"][0]["objects"][0]["e"] == 5
        assert json_obj["test_tool"]["test_result"][0]["objects"][0]["f"] == "hello"

        environment.remove("test_tool", "test_result")
        assert environment.is_empty()

        environment.add_objects(
            "test_tool2",
            "test_result2",
            [{"a": 1, "b": 2}],
            metadata={"item_number": "first"},
        )
        assert "test_tool2" in environment.environment
        assert "test_result2" in environment.environment["test_tool2"]
        assert (
            environment.environment["test_tool2"]["test_result2"][0]["objects"][0]["a"]
            == 1
        )
        assert (
            environment.environment["test_tool2"]["test_result2"][0]["objects"][0]["b"]
            == 2
        )
        assert (
            environment.environment["test_tool2"]["test_result2"][0]["metadata"][
                "item_number"
            ]
            == "first"
        )

        environment.add_objects(
            "test_tool2",
            "test_result2",
            [{"c": 1, "d": 2}],
            metadata={"item_number": "second"},
        )
        assert (
            environment.environment["test_tool2"]["test_result2"][1]["objects"][0]["c"]
            == 1
        )
        assert (
            environment.environment["test_tool2"]["test_result2"][1]["objects"][0]["d"]
            == 2
        )
        assert (
            environment.environment["test_tool2"]["test_result2"][1]["metadata"][
                "item_number"
            ]
            == "second"
        )

        assert (
            environment.environment["test_tool2"]["test_result2"][0]["objects"][0]["a"]
            == 1
        )
        assert (
            environment.environment["test_tool2"]["test_result2"][0]["objects"][0]["b"]
            == 2
        )

        environment.remove("test_tool2", "test_result2", 1)
        assert environment.environment["test_tool2"]["test_result2"] != []
        assert (
            environment.environment["test_tool2"]["test_result2"][0]["objects"][0]["a"]
            == 1
        )
        assert (
            environment.environment["test_tool2"]["test_result2"][0]["objects"][0]["b"]
            == 2
        )
        assert (
            environment.environment["test_tool2"]["test_result2"][0]["metadata"][
                "item_number"
            ]
            == "first"
        )
        assert len(environment.environment["test_tool2"]["test_result2"]) == 1
