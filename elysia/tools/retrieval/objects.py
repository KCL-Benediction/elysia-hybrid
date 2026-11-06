import uuid

from weaviate.classes.query import Filter, QueryReference

from elysia.objects import Retrieval

# Objects
from elysia.tools.objects import (
    BoringGeneric,
    Conversation,
    Document,
    Ecommerce,
    EpicGeneric,
    Message,
    Ticket,
)

# Client Manager
from elysia.util.client import ClientManager

# Utilities
from elysia.util.parsing import format_dict_to_serialisable


class EpicGenericRetrieval(EpicGeneric, Retrieval):
    def __init__(
        self,
        objects: list[dict],
        metadata: dict,
        mapping: dict | None = None,
    ):
        # EpicGeneric.__init__(self, objects, metadata, mapping)
        Retrieval.__init__(
            self,
            objects,
            payload_type="epic_generic",
            metadata=metadata,
            mapping=mapping,
        )


class BoringGenericRetrieval(BoringGeneric, Retrieval):
    def __init__(
        self,
        objects: list[dict],
        metadata: dict,
        mapping: dict | None = None,
    ):
        # BoringGeneric.__init__(self, objects, metadata, mapping)
        Retrieval.__init__(
            self,
            objects,
            payload_type="boring_generic",
            metadata=metadata,
            mapping=mapping,
        )


class EcommerceRetrieval(Ecommerce, Retrieval):
    def __init__(
        self,
        objects: list[dict],
        metadata: dict,
        mapping: dict | None = None,
    ):
        # Ecommerce.__init__(self, objects, metadata, mapping)
        Retrieval.__init__(
            self,
            objects,
            payload_type="ecommerce",
            metadata=metadata,
            mapping=mapping,
        )


class TicketRetrieval(Ticket, Retrieval):
    def __init__(
        self,
        objects: list[dict],
        metadata: dict,
        mapping: dict | None = None,
    ):
        # Ticket.__init__(self, objects, metadata, mapping)
        Retrieval.__init__(
            self,
            objects,
            payload_type="ticket",
            metadata=metadata,
            mapping=mapping,
        )


class MessageRetrieval(Message, Retrieval):
    def __init__(
        self,
        objects: list[dict],
        metadata: dict,
        mapping: dict | None = None,
    ):
        for obj in objects:
            obj["relevant"] = False

        # Message.__init__(self, objects, metadata, mapping)
        Retrieval.__init__(
            self,
            objects,
            payload_type="message",
            metadata=metadata,
            mapping=mapping,
            unmapped_keys=["uuid", "summary", "collection_name", "relevant"],
        )


class ConversationRetrieval(Conversation, Retrieval):
    def __init__(
        self,
        objects: list[dict],
        metadata: dict,
        mapping: dict | None = None,
    ):
        # Conversation.__init__(self, objects, metadata, mapping)
        Retrieval.__init__(
            self,
            objects,
            payload_type="conversation",
            metadata=metadata,
            mapping=mapping,
            unmapped_keys=["uuid", "summary", "collection_name", "relevant"],
        )
        self.async_init_completed = False

    async def async_init(self, client_manager: ClientManager):
        if not self.async_init_completed:
            await self._return_all_messages_in_conversation(client_manager)

    async def _fetch_items_in_conversation(
        self,
        conversation_id: str,
        metadata: dict,
        message_index: int,
        client_manager: ClientManager,
    ):
        """
        Use Weaviate to fetch all messages in a conversation based on the conversation ID.
        """
        assert (
            "collection_name" in metadata
        ), "collection_name is required for fetching other messages in a conversation"

        async with client_manager.connect_to_async_client() as client:
            collection = client.collections.get(metadata["collection_name"])
            items_in_conversation = await collection.query.fetch_objects(
                filters=Filter.by_property("conversation_id").equal(conversation_id)
            )

        output = []
        for obj in items_in_conversation.objects:
            output.append(obj.properties)
            output[-1]["uuid"] = str(obj.uuid)
            if output[-1]["message_index"] == message_index:
                output[-1]["relevant"] = True
            else:
                output[-1]["relevant"] = False

        return output

    async def _return_all_messages_in_conversation(self, client_manager: ClientManager):
        """
        Return all messages in a conversation based on the response from Weaviate.
        """

        returned_objects = []
        for o in self.objects:
            items_in_conversation = await self._fetch_items_in_conversation(
                o["conversation_id"], self.metadata, o["message_index"], client_manager
            )
            items_in_conversation.sort(key=lambda x: int(x["message_index"]))
            returned_objects.append(
                {
                    "messages": items_in_conversation,
                    "conversation_id": o["conversation_id"],
                }
            )

        self.objects = returned_objects
        self.async_init_completed = True

        return returned_objects

    def to_json(self, mapping: bool = False):
        assert (
            self.async_init_completed
        ), "ERROR: ConversationRetrieval not initialized, need to run .async_init(client_manager)"

        if self.mapping is not None and mapping:
            output_objects = []
            for obj in self.objects:  # outer level, conversation
                output_objects.append(
                    {
                        "conversation_id": obj["conversation_id"],
                        "messages": [],
                    }
                )
                for message in obj["messages"]:  # inner level, message
                    output_objects[-1]["messages"].append(
                        {
                            key: message[self.mapping[key]]
                            for key in self.mapping
                            if self.mapping[key] != ""
                        }
                    )
                    output_objects[-1]["messages"][-1].update(
                        {
                            key: message[key]
                            for key in self.unmapped_keys
                            if key in message
                        }
                    )
        else:
            output_objects = self.objects

        for object in output_objects:
            for message in object["messages"]:
                format_dict_to_serialisable(message)

        return output_objects


class DocumentRetrieval(Document, Retrieval):
    def __init__(
        self,
        objects: list[dict],
        metadata: dict,
        mapping: dict | None = None,
    ):
        assert (
            "collection_name" in metadata
        ), "collection_name is required for DocumentRetrieval"

        if "chunked" not in metadata:
            metadata["chunked"] = False

        for obj in objects:
            obj["collection_name"] = metadata["collection_name"]
            if "chunk_spans" not in obj:
                obj["chunk_spans"] = []

        # Document.__init__(self, objects, metadata, mapping)
        Retrieval.__init__(
            self,
            objects,
            payload_type="document",
            metadata=metadata,
            mapping=mapping,
            unmapped_keys=[
                "uuid",
                "summary",
                "collection_name",
                "chunk_spans",
                "chunk_uuid",
            ],
        )
        self.async_init_completed = False

    async def async_init(self, client_manager: ClientManager):
        if not self.async_init_completed:
            await self._get_related_documents(client_manager)

    async def _get_related_documents(self, client_manager: ClientManager):
        """
        Get the related full documents for the chunked documents in the DocumentRetrieval object.
        """
        if self.metadata["chunked"]:
            chunked_collection_name = (
                f"ELYSIA_CHUNKED_{self.metadata['collection_name'].lower()}__"
            )
            async with client_manager.connect_to_async_client() as client:
                if await client.collections.exists(chunked_collection_name):
                    chunked_collection = client.collections.get(chunked_collection_name)

                    # re-retrieve the exact same items but with the full document references
                    # TODO: this is unnecessary, in the first retrieval we should have already retrieved the full documents
                    # here we just add them to the objects
                    # TODO when refactoring the query code
                    chunked_response = (
                        await chunked_collection.query.fetch_objects_by_ids(
                            [object["uuid"] for object in self.objects],
                            return_references=QueryReference(link_on="fullDocument"),
                        )
                    )

                    # Loop over all references in this new response and add them to the full_docs dictionary
                    full_docs = {}
                    for object in chunked_response.objects:
                        # retrieve cross references from this current chunked response object
                        if "fullDocument" in object.references:
                            references = object.references["fullDocument"].objects

                            # this list is length one (only one full doc per chunk)
                            for full_document in references:

                                # each chunk is attached to a full doc, but can have multiple chunks per full doc
                                if str(full_document.uuid) not in full_docs:
                                    full_docs[str(full_document.uuid)] = {
                                        **full_document.properties,
                                        "uuid": str(full_document.uuid),
                                        "collection_name": self.metadata[
                                            "collection_name"
                                        ],
                                        "chunk_spans": [],
                                    }

                                # chunk comes from `object` which is the chunk (outer level loop)
                                full_docs[str(full_document.uuid)][
                                    "chunk_spans"
                                ].append(
                                    {
                                        "start": object.properties["chunk_spans"][0],
                                        "end": object.properties["chunk_spans"][1],
                                        "uuid": str(object.uuid),
                                    }
                                )

                    self.full_documents = list(full_docs.values())
                else:
                    print(
                        "WARNING: DocumentRetrieval has metadata['chunked'] set to True, but the chunked collection does not exist. Returning chunks only."
                    )
                    self.full_documents = self.objects
        else:
            self.full_documents = self.objects
        self.async_init_completed = True

    def full_documents_to_json(self, mapping: bool = False):
        assert all(
            isinstance(obj, dict) for obj in self.full_documents
        ), "All objects must be dictionaries"

        if mapping and self.mapping is not None:
            output_objects = []
            for obj in self.full_documents:
                output_objects.append(
                    {
                        key: obj[self.mapping[key]]
                        for key in self.mapping
                        if self.mapping[key] != ""
                    }
                )
                output_objects[-1].update(
                    {key: obj[key] for key in self.unmapped_keys if key in obj}
                )
        else:
            output_objects = self.full_documents

        for object in output_objects:
            format_dict_to_serialisable(object)

        return output_objects

    async def to_frontend(self, user_id: str, conversation_id: str, query_id: str):
        """
        Needs re-definition of the to_frontend method because the frontend receives full documents,
        whereas the LLM receives the chunks.
        So to_json() outputs the chunks (to the LLM)
        But the to_frontend() outputs the full documents and the chunk spans.
        """
        if self.metadata["chunked"] and not self.async_init_completed:
            raise Exception(
                "ERROR: Documents are chunked and DocumentRetrieval not initialized. "
                "Need to run .async_init(client_manager) to retrieve the full documents attached to the chunks. "
                "Otherwise set metadata['chunked'] to False"
            )

        payload = {
            "type": self.payload_type,
            "objects": (
                self.full_documents_to_json(mapping=True)
                if self.metadata["chunked"] and self.async_init_completed
                else self.to_json(mapping=True)
            ),
            "metadata": self.metadata,
        }

        if "code" in self.metadata:
            payload["code"] = self.metadata["code"]

        return {
            "type": self.frontend_type,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "query_id": query_id,
            "id": self.frontend_type[:3] + "-" + str(uuid.uuid4()),
            "payload": payload,
        }


class Aggregation(Retrieval):
    def __init__(
        self,
        objects: list[dict],
        metadata: dict = {},
        name: str | None = None,
    ):
        if name is None and "collection_name" in metadata:
            name = metadata["collection_name"]
        elif name is None:
            name = "generic"

        # TODO: talk to edward about adding num_items back
        # for obj in objects:
        #     for collection_name, collection_data in obj.items():
        #         if "num_items" in collection_data.keys():
        #             del collection_data["num_items"]

        Retrieval.__init__(
            self,
            objects=objects,
            payload_type="aggregation",
            metadata=metadata,
            name=name,
        )

    def llm_parse(self):
        out = ""
        if "collection_name" in self.metadata:
            out += f"\nAggregated collection: '{self.metadata['collection_name']}'"

            count = {}
            if len(self.objects) > 0:
                for metric in self.objects[0][self.metadata["collection_name"]]:
                    if metric != "ELYSIA_NUM_ITEMS":
                        num_values = len(
                            self.objects[0][self.metadata["collection_name"]][metric][
                                "values"
                            ]
                        )
                        count[metric] = num_values

                for metric in count:
                    out += f", returned {count[metric]} values for {metric}."
                if any(count[metric] == 0 for metric in count):
                    out += f" For those metrics with 0 objects, judge the aggregation code that was created, and evaluate whether it was appropriate for the collection/metric, the user prompt, and the data available."
                    out += f" If it seemed innappropriate, you can choose to try again if you think it can still be completed (or there is more to do)."
            else:
                out += f" but no objects were returned."
                out += f" Since it had no objects, judge the aggregation code that was created, and evaluate whether it was appropriate for the collection, the user prompt, and the data available."
                out += f" If it seemed innappropriate, you can choose to try again if you think it can still be completed (or there is more to do)."

            if "groupby_name" in self.metadata:
                out += f"\nGrouped by property '{self.metadata['groupby_name']}'"
            if "metrics" in self.metadata:
                out += f"\nReturned metrics for property(-ies) '{self.metadata['metrics']}'"
            if "impossible" in self.metadata:
                if "collection_name" in self.metadata:
                    out += f"\nThis attempt at aggregating the collection: {self.metadata['collection_name']} was deemed impossible."
                out += f"The user prompt was: '{self.metadata['impossible']}', which the aggregation model deemed impossible to complete."
                if "impossible_reasoning" in self.metadata:
                    out += f"\nReasoning for impossibility: {self.metadata['impossible_reasoning']}"
            if "assertion_error_message" in self.metadata:
                out += f"\nWhen aggregating this collection ({self.metadata['collection_name']}), the following assertion error occurred:"
                out += f"\n<assertion_error_message>\n  {self.metadata['assertion_error_message']}\n</assertion_error_message>\n"
                out += f" You should judge whether this error is avoidable, and choose your task accordingly."
                out += f" An assertion error is _usually_ fixable by changing the aggregation code (either now if that is your task, or in the future if you are not tasked with writing code for aggregating a collection currently)."
                out += f" For example, if you are choosing a function to use (you are making a decision), you are not writing the aggregation code, so do not try to fix it."
                out += f" If you are writing the aggregation code, you should try to fix it, based on this error message."
            if "error_message" in self.metadata:
                out += f"\nThe following GENERIC error occurred when querying this collection ({self.metadata['collection_name']}):"
                out += f" \n<error_message>\n  {self.metadata['error_message']}\n</error_message>\n"
                out += f" You should judge whether this error is avoidable, and choose your task accordingly."
                out += f" These kind of errors are usually due to a problem outside of your control, such as a problem with the database or the internet connection."
                out += f" You should probably not repeat this task/try to fix this error, but instead communicate apologies to the user and suggest alternatives based on this error."
                out += f" Unless this is a Weaviate client error (such as a timeout/GRPC error), then you should try to repeat this task as it likely won't happen again."
            if "aggregation_output" in self.metadata:
                out += f"\nThe aggregation query used was:\n{self.metadata['aggregation_output']}"
        return out
