import uuid

from elysia.util.parsing import format_dict_to_serialisable


class Branch:
    """
    These branches are searched in advance of the tree being run, iterating through code and function calls.
    Used to build the decision tree display on the frontend.
    """

    def __init__(self, updates: dict):
        self.updates = updates


class Tool:
    """
    The generic Tool class, which will be a superclass of any tools used by Elysia.
    """

    def __init__(
        self,
        name: str,
        description: str,
        status: str = "",
        inputs: dict = {},
        end: bool = False,
        rule: bool = False,
        **kwargs,
    ):
        """
        Args:
            name (str): The name of the tool. Required.
            description (str): A detailed description of the tool to give to the LLM. Required.
            status (str): A status update message to display while the tool is running. Optional, defaults to "Running {name}...".
            inputs (dict): A dictionary of inputs for the tool, with the following structure:
                ```python
                {
                    input_name: {
                        "description": str,
                        "type": str,
                        "default": str,
                        "required": bool
                    }
                }
                ```
            end (bool): Whether the tool is an end tool. Optional, defaults to False.
            rule (bool): Whether the tool is a rule tool. Optional, defaults to False.
        """
        self.name = name
        self.description = description
        self.inputs = inputs
        self.end = end
        self.rule = rule

        if status == "":
            self.status = f"Running {self.name}..."
        else:
            self.status = status

    def get_default_inputs(self):
        return {
            key: value["default"] if "default" in value else None
            for key, value in self.inputs.items()
        }

    async def run_if_true(
        self,
        tree_data,
        base_lm,
        complex_lm,
        client_manager,
    ):
        """
        This method is called to check if the tool should be run automatically.
        If this returns `True`, then the tool is immediately called at the start of the tree.
        Otherwise it does not appear in the decision tree.

        This must be an async function.

        Args:
            tree_data (TreeData): The tree data object.
            base_lm (LM): The base language model, a dspy.LM object.
            complex_lm (LM): The complex language model, a dspy.LM object.
            client_manager (ClientManager): The client manager, a way of interfacing with a Weaviate client.

        Returns:
            bool: True if the tool should be run automatically, False otherwise.
        """
        return False

    async def is_tool_available(
        self,
        tree_data,
        base_lm,
        complex_lm,
        client_manager,
    ):
        """
        This method is called to check if the tool is available.
        If this returns `True`, then the tool is available to be used by the LLM.
        Otherwise it does not appear in the decision tree.

        The difference between this and `run_if_true` is that `run_if_true` will _always_ run the __call__ method if it returns `True`,
        even if the LLM does not choose to use the tool.

        This must be an async function.

        Args:
            tree_data (TreeData): The tree data object.
            base_lm (LM): The base language model, a dspy.LM object.
            complex_lm (LM): The complex language model, a dspy.LM object.
            client_manager (ClientManager): The client manager, a way of interfacing with a Weaviate client.

        Returns:
            bool: True if the tool is available, False otherwise.
        """
        return True

    async def __call__(
        self,
        tree_data,
        base_lm,
        complex_lm,
        client_manager,
    ):
        """
        This method is called to run the tool.

        This must be an async generator, so objects must be yielded and not returned.

        Args:
            tree_data (TreeData): The data from the decision tree, includes the environment, user prompt, etc.
                See the `TreeData` class for more details.
            base_lm (LM): The base language model, a dspy.LM object.
            complex_lm (LM): The complex language model, a dspy.LM object.
            client_manager (ClientManager): The client manager, a way of interfacing with a Weaviate client.
        """
        pass


class Reasoning:
    def __init__(self, reasoning: str):
        self.reasoning = reasoning
        self.type = "reasoning"

    def to_json(self):
        return {"reasoning": self.reasoning}


class Return:
    """
    A Return object is something that is returned to the frontend.
    This kind of object is frontend-aware.
    """

    def __init__(self, frontend_type: str, payload_type: str):
        self.frontend_type = frontend_type  # frontend identifier
        self.payload_type = payload_type  # backend identifier


class Text(Return):
    """
    Frontend Return Type 1: Text
    Objects is usually a one-element list containing a dict with a "text" key only.
    But is not limited to this.
    """

    def __init__(self, payload_type: str, objects: list[dict], metadata: dict = {}):
        Return.__init__(self, "text", payload_type)
        self.objects = objects
        self.metadata = metadata
        self.text = objects[0]["text"]

    def to_json(self):
        return {
            "type": self.payload_type,
            "metadata": self.metadata,
            "objects": self.objects,
        }

    async def to_frontend(
        self,
        user_id: str,
        conversation_id: str,
        query_id: str,
    ):
        return {
            "type": self.frontend_type,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "query_id": query_id,
            "payload": self.to_json(),
        }


class Response(Text):
    def __init__(self, text: str):
        Text.__init__(self, "response", [{"text": text}])
        self.text = text


class Update(Return):
    """
    Frontend Return Type 2: Update
    An update is something that is not _displayed_ on the frontend, but gives information to the frontend.
    E.g. a warning, error, status message, etc.
    """

    def __init__(self, frontend_type: str, object: dict):
        Return.__init__(self, frontend_type, "update")
        self.object = object

    def to_json(self):
        return self.object

    async def to_frontend(self, conversation_id: str, query_id: str):
        return {
            "type": self.frontend_type,
            "conversation_id": conversation_id,
            "query_id": query_id,
            "id": self.frontend_type[:3] + "-" + str(uuid.uuid4()),
            "payload": self.to_json(),
        }


class Status(Update):
    """
    Status message to be sent to the frontend for real-time updates in words.
    """

    def __init__(self, text: str):
        self.text = text
        Update.__init__(self, "status", {"text": text})


class Warning(Update):
    """
    Warning message to be sent to the frontend.
    """

    def __init__(self, text: str):
        self.text = text
        Update.__init__(self, "warning", {"text": text})


class Error(Update):
    """
    Error message to be sent to the frontend.
    """

    def __init__(self, text: str):
        self.text = text
        Update.__init__(self, "error", {"text": text})


class Completed(Update):
    """
    Completed message to be sent to the frontend (tree is complete all recursions).
    """

    def __init__(self):
        Update.__init__(self, "completed", {})


class Result(Return):
    """
    Result objects are returned to the frontend.
    These are displayed on the frontend.
    E.g. a table, a chart, a text response, etc.

    You can yield a `Result` directly, and specify the `type` and `name` of the result.
    """

    def __init__(
        self,
        objects: list[dict],
        metadata: dict = {},
        payload_type: str = "default",
        name: str = "generic",
        mapping: dict | None = None,
        llm_message: str | None = None,
        unmapped_keys: list[str] = [],
    ):
        """
        Args:
            objects (list[dict]): The objects attached to this result.
            payload_type: (str): Identifier for the type of result.
            metadata (dict): The metadata attached to this result,
                for example, query used, time taken, any other information not directly within the objects
            name (str): The name of the result, e.g. this could be the name of the collection queried.
                Used to index the result in the environment.
            mapping (dict | None): A mapping of the objects to the frontend.
                Essentially, if the objects are going to be displayed on the frontend, the frontend has specific keys that it wants the objects to have.
                This is a dictionary that maps from frontend keys to the object keys.
            llm_message (str | None): A message to be displayed to the LLM to help it parse the result.
                You can use the following placeholders that will automatically be replaced with the correct values:

                - {type}: The type of the object
                - {name}: The name of the object
                - {num_objects}: The number of objects in the object
                - {metadata_key}: Any key in the metadata dictionary
            unmapped_keys (list[str]): A list of keys that are not mapped to the frontend.
        """
        Return.__init__(self, "result", payload_type)
        self.objects = objects
        self.metadata = metadata
        self.name = name
        self.mapping = mapping
        self.llm_message = llm_message
        self.unmapped_keys = unmapped_keys

    def __len__(self):
        return len(self.objects)

    # TODO: _remove duplicates is unused, do we need it?
    def _remove_duplicates(self, objects: list[dict | str]):
        unique_objects = []
        seen = set()

        for obj in objects:
            if isinstance(obj, dict):
                # Convert dict to a string representation for comparison
                obj_str = str(sorted(obj.items()))
            else:
                obj_str = str(obj)

            if obj_str not in seen:
                seen.add(obj_str)
                unique_objects.append(obj)

        return unique_objects

    def format_llm_message(self):
        """
        llm_message is a string that is used to help the LLM parse the output of the tool.
        It is a placeholder for the actual message that will be displayed to the user.

        You can use the following placeholders:

        - {payload_type}: The type of the object
        - {name}: The name of the object
        - {num_objects}: The number of objects in the object
        - {metadata_key}: Any key in the metadata dictionary
        """
        return self.llm_message.format_map(
            {
                "payload_type": self.payload_type,
                "name": self.name,
                "num_objects": len(self),
                **self.metadata,
            }
        )

    def do_mapping(self, objects: list[dict]):

        output_objects = []
        for obj in objects:
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

        return output_objects

    def to_json(self, mapping: bool = False):
        """
        Convert the result to a list of dictionaries.

        Args:
            mapping (bool): Whether to map the objects to the frontend.
                This will use the `mapping` dictionary created on initialisation of the `Result` object.
                If `False`, the objects are returned as is.
                Defaults to `False`.

        Returns:
            list[dict]: A list of dictionaries, which can be serialised to JSON.
        """
        assert all(
            isinstance(obj, dict) for obj in self.objects
        ), "All objects must be dictionaries"

        if mapping and self.mapping is not None:
            output_objects = self.do_mapping(self.objects)
        else:
            output_objects = self.objects

        for object in output_objects:
            format_dict_to_serialisable(object)

        return output_objects

    async def to_frontend(
        self,
        user_id: str,
        conversation_id: str,
        query_id: str,
    ):
        """
        Convert the result to a frontend payload.
        This is a wrapper around the `to_json` method.
        But the objects and metadata are inside a `payload` key, which also includes a `type` key,
        being the frontend identifier for the type of payload being sent.
        (e.g. `ticket`, `ecommerce`, `message`, etc.)

        The outside of the payload also contains the user_id, conversation_id, and query_id.

        Args:
            user_id (str): The user ID.
            conversation_id (str): The conversation ID.
            query_id (str): The query ID.

        Returns:
            dict: The frontend payload, which is a dictionary with the following structure:
                ```python
                {
                    "type": "result",
                    "user_id": str,
                    "conversation_id": str,
                    "query_id": str,
                    "id": str,
                    "payload": dict = {
                        "type": str,
                        "objects": list[dict],
                        "metadata": dict,
                    },
                }
                ```
        """
        objects = self.to_json(mapping=True)
        if len(objects) == 0:
            return

        payload = {
            "type": self.payload_type,
            "objects": objects,
            "metadata": self.metadata,
        }

        return {
            "type": self.frontend_type,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "query_id": query_id,
            "id": self.frontend_type[:3] + "-" + str(uuid.uuid4()),
            "payload": payload,
        }

    def llm_parse(self):
        """
        This method is called when the result is displayed to the LLM.
        It is used to display custom information to the LLM about the result.
        If `llm_message` was defined, then the llm message is formatted using the placeholders.
        Otherwise a default message is used.

        Returns:
            str: The formatted llm message.
        """

        if self.llm_message is not None:
            return self.format_llm_message()
        else:
            # Default message
            return f"Displayed: A {self.payload_type} object with {len(self.objects)} objects."


# Retrieval/Aggregation/Anything we used code to get data
class Retrieval(Result):
    """
    Store of returned objects from a query/aggregate/any displayed results.
    """

    def __init__(
        self,
        objects: list[dict],
        payload_type: str = "default",
        name: str | None = None,
        metadata: dict = {},
        mapping: dict | None = None,
        unmapped_keys: list[str] = ["uuid", "summary", "collection_name"],
    ):
        if name is None and "collection_name" in metadata:
            name = metadata["collection_name"]
        elif name is None:
            name = "default"

        Result.__init__(
            self,
            objects=objects,
            payload_type=payload_type,
            metadata=metadata,
            name=name,
            mapping=mapping,
            unmapped_keys=unmapped_keys,
        )

    def add_summaries(self, summaries: list[str] = []):
        for i, obj in enumerate(self.objects):
            if i < len(summaries):
                obj["ELYSIA_SUMMARY"] = summaries[i]
            else:
                obj["ELYSIA_SUMMARY"] = ""

    def llm_parse(self):
        out = ""
        count = len(self.objects)

        if "collection_name" in self.metadata:
            if count != 0:
                out += f"\nQueried collection: '{self.metadata['collection_name']}' and returned {count} objects, "
            else:
                out += f"\nQueried collection: '{self.metadata['collection_name']}' but no objects were returned."
                out += f" Since it had no objects, judge the query that was created, and evaluate whether it was appropriate for the collection, the user prompt, and the data available."
                out += f" If it seemed innappropriate, you can choose to try again if you think it can still be completed (or there is more to do)."
        if "return_type" in self.metadata:
            out += f"\nReturned with type '{self.metadata['return_type']}', "
        if "output_type" in self.metadata:
            out += f"\noutputted '{'itemised summaries' if self.metadata['output_type'] == 'summary' else 'original objects'}'\n"
        if "query_text" in self.metadata:
            out += f"\nSearch terms: '{self.metadata['query_text']}'"
        if "query_type" in self.metadata:
            out += f"\nType of query: '{self.metadata['query_type']}'"
        if "impossible" in self.metadata:
            out += f"\nImpossible prompt: '{self.metadata['impossible']}'"
            if "collection_name" in self.metadata:
                out += f"\nThis attempt at querying the collection: {self.metadata['collection_name']} was deemed impossible."
            if "impossible_reason" in self.metadata:
                out += f"\nReasoning for impossibility: {self.metadata['impossible_reason']}"
        if "assertion_error_message" in self.metadata:
            out += f"\nWhen querying this collection ({self.metadata['collection_name']}), the following ASSERTION error occurred:"
            out += f"\n<assertion_error_message>\n  {self.metadata['assertion_error_message']}\n</assertion_error_message>\n"
            out += f"You should judge whether this error is avoidable, and choose your task accordingly."
            out += f"An assertion error is _usually_ fixable by changing the query code (either now if that is your task, or in the future if you are not tasked with writing code for querying a collection currently)."
            out += f"For example, if you are choosing a function to use (you are making a decision), you are not writing the query code, so do not try to fix it."
            out += f"If you are writing the query code, you should try to fix it, based on this error message."
        if "error_message" in self.metadata:
            out += f"\nThe following GENERIC error occurred when querying this collection ({self.metadata['collection_name']}):"
            out += f"\n<error_message>\n  {self.metadata['error_message']}\n</error_message>\n"
            out += f"You should judge whether this error is avoidable, and choose your task accordingly."
            out += f"These kind of errors are usually due to a problem outside of your control, such as a problem with the database or the internet connection."
            out += f"You should probably not repeat this task/try to fix this error, but instead communicate apologies to the user and suggest alternatives based on this error."
            out += f"Unless this is a Weaviate client error (such as a timeout/GRPC error), then you should try to repeat this task as it likely won't happen again."
        if "query_output" in self.metadata:
            out += f"\nThe query used was:\n{self.metadata['query_output']}"
        return out

    async def to_frontend(
        self,
        user_id: str,
        conversation_id: str,
        query_id: str,
    ):
        objects = self.to_json(mapping=True)
        if len(objects) == 0:
            return

        payload = {
            "type": self.payload_type,
            "objects": objects,
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
