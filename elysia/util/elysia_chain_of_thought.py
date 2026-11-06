from typing import Type
from copy import copy

import dspy
from dspy.primitives.program import Module
from dspy.signatures.signature import Signature, ensure_signature
from elysia.tree.objects import TreeData, Atlas


class ElysiaChainOfThought(Module):
    """
    A custom reasoning DSPy module that reasons step by step in order to predict the output of a task.
    It will automatically include the most relevant inputs:
    - The user's prompt
    - The conversation history
    - The atlas

    And you can also include optional inputs (by setting their boolean flags on initialisation to `True`):
    - The environment
    - The collection schemas
    - The tasks completed

    You can also specify `collection_names` to only include certain collections in the collection schemas.

    It will automatically output:
    - The reasoning (model step by step reasoning)
    - Whether the task is impossible (boolean)

    And optionally output (by setting the boolean flags on initialisation to `True`):
    - A message update (if `message_update` is `True`), a brief 'update' message to the user.

    You can use this module by calling the `.aforward()` method, passing all your *new* inputs as keyword arguments.
    You do not need to include keyword arguments for the other inputs, like the `environment`.

    Example:
    ```python
    my_module = ElysiaChainOfThought(
        signature=...,
        tree_data=...,
        message_update=True,
        environment=True,
        collection_schemas=True,
        tasks_completed=True,
    )
    my_module.aforward(input1=..., input2=...)
    ```
    """

    def __init__(
        self,
        signature: Type[Signature],
        tree_data: TreeData,
        message_update: bool = True,
        environment: bool = False,
        collection_schemas: bool = False,
        tasks_completed: bool = False,
        collection_names: list[str] = [],
        **config,
    ):
        """
        Args:
            signature (Type[dspy.Signature]): The signature of the module.
            tree_data (TreeData): Required. The tree data from the Elysia decision tree.
                Used to input the current state of the tree into the prompt.
                If you are using this module as part of a tool, the `tree_data` is an input to the tool call.
            message_update (bool): Whether to include a message update input.
                If True, the LLM output will include a brief 'update' message to the user.
                This describes the current action the LLM is performing.
                Designed to increase interactivity and provide the user with information before the final output.
            environment (bool): Whether to include an environment input.
                If True, the module will include the currently stored data from previous tasks and actions into the prompt.
                This is useful so that the LLM knows what has already been done, and can avoid repeating actions.
                Or to use information from the environment to perform the new action.
            collection_schemas (bool): Whether to include a collection schema input.
                If True, the module will include the preprocessed collection schemas in the prompt input.
                This is useful so that the LLM knows the structure of the collections, if querying or similar.
                Use this sparingly, as it will use a large amount of tokens.
                You can specify `collection_names` to only include certain collections in this schema.
            tasks_completed (bool): Whether to include a tasks completed input.
                If True, the module will include the list of tasks completed input.
                This is a nicely formatted list of the tasks that have been completed, with the reasoning for each task.
                This is used so that the LLM has a 'stream of consciousness' of what has already been done,
                as well as to stop it from repeating actions.
                Other information is included in the `tasks_completed` field that format outputs from previous tasks.
                This is useful for continuing a decision logic across tasks, or to reinforce key information.
            collection_names (list[str]): A list of collection names to include in the prompt.
                If provided, this will modify the collection schema input to only include the collections in this list.
                This is useful if you only want to include certain collections in the prompt.
                And to reduce token usage.
            **config: The configuration for the module.
        """

        super().__init__()

        signature = ensure_signature(signature)

        # Create a shallow copy of the tree_data
        self.tree_data = copy(tree_data)

        # Note which inputs are required
        self.message_update = message_update
        self.environment = environment
        self.collection_schemas = collection_schemas
        self.tasks_completed = tasks_completed
        self.collection_names = collection_names

        # == Inputs ==

        # -- User Prompt --
        user_prompt_desc = (
            "The user's original question/prompt that needs to be answered. "
            "This, possibly combined with the conversation history, will be used to determine your current action."
        )
        user_prompt_prefix = "${user_prompt}"
        user_prompt_field: str = dspy.InputField(
            prefix=user_prompt_prefix, desc=user_prompt_desc
        )

        # -- Conversation History --
        conversation_history_desc = (
            "Previous messages between user and assistant in chronological order: "
            "[{'role': 'user'|'assistant', 'content': str}] "
            "Use this to maintain conversation context and avoid repetition."
        )
        conversation_history_prefix = "${conversation_history}"
        conversation_history_field: list[dict] = dspy.InputField(
            prefix=conversation_history_prefix, desc=conversation_history_desc
        )

        # -- Atlas --
        atlas_desc = (
            "Your guide to how you should proceed as an agent in this task. "
            "This is pre-defined by the user."
        )
        atlas_prefix = "${atlas}"
        atlas_field: Atlas = dspy.InputField(prefix=atlas_prefix, desc=atlas_desc)

        # == Outputs ==

        # -- Reasoning Field --
        reasoning_desc = (
            "Reasoning: Repeat relevant parts of the any context within your environment, "
            "use this to think step by step in order to answer the query."
        )
        reasoning_prefix = "${reasoning}"
        reasoning_field: str = dspy.OutputField(
            prefix=reasoning_prefix, desc=reasoning_desc
        )

        # -- Impossible Field --
        impossible_desc = (
            "Given the actions you have available, and the environment/information. "
            "Is the task impossible to complete? "
            "I.e., do you wish that you had a different task to perform/choose from and hence should return to the base of the decision tree?"
        )
        impossible_prefix = "${impossible}"
        impossible_field: bool = dspy.OutputField(
            prefix=impossible_prefix, desc=impossible_desc
        )

        # -- Add to Signature --
        extended_signature = signature.prepend(
            name="user_prompt", field=user_prompt_field, type_=str
        )
        extended_signature = extended_signature.append(
            name="conversation_history",
            field=conversation_history_field,
            type_=list[dict],
        )
        extended_signature = extended_signature.append(
            name="atlas", field=atlas_field, type_=Atlas
        )
        extended_signature = extended_signature.prepend(
            name="reasoning", field=reasoning_field, type_=str
        )
        extended_signature = extended_signature.append(
            name="impossible", field=impossible_field, type_=bool
        )

        # == Optional Inputs / Outputs ==

        # -- Environment Input --
        if environment:
            environment_desc = (
                "Information gathered from completed tasks. "
                "Empty if no data has been retrieved yet. "
                "Use to determine if more information is needed. "
                "Additionally, use this as a reference to determine if you have already completed a task/what items are already available, to avoid repeating actions. "
                "All items here are already shown to the user, so do not repeat information from these fields unless summarising, providing extra information or otherwise. "
                "E.g., do not list out anything from here, only provide new content to the user."
            )
            environment_prefix = "${environment}"
            environment_field: dict = dspy.InputField(
                prefix=environment_prefix, desc=environment_desc
            )
            extended_signature = extended_signature.append(
                name="environment", field=environment_field, type_=dict
            )

        # -- Collection Schema Input --
        if collection_schemas:
            collection_schemas_desc = (
                "Metadata about available collections and their schemas: "
                "{ name: { summary, fields: { min, max, type, etc. } } "
                "Where name is the name of the collection, and summary is a short description of the collection. "
                "The statistics such as min/max is of the data in the field. If this is numerical, this is the range of values in the data. "
                "If string, it is the length of the string. If it is a list, it is related to the length of the list. "
                "Use to determine either determine the user's request is possible, or if your task needs it, use it for information. "
            )
            collection_schemas_prefix = "${collection_schemas}"
            collection_schemas_field: dict = dspy.InputField(
                prefix=collection_schemas_prefix, desc=collection_schemas_desc
            )
            extended_signature = extended_signature.append(
                name="collection_schemas", field=collection_schemas_field, type_=dict
            )

        # -- Tasks Completed Input --
        if tasks_completed:
            tasks_completed_desc = (
                "Which tasks have been completed in order. "
                "These are numbered so that higher numbers are more recent. "
                "Separated by prompts (so you should identify the prompt you are currently working on to see what tasks have been completed so far) "
                "Also includes reasoning for each task, to continue a decision logic across tasks. "
                "Use this to determine whether future searches, for this prompt are necessary, and what task(s) to choose. "
                "It is IMPORTANT that you separate what actions have been completed for which prompt, so you do not think you have failed an attempt for a different prompt."
            )
            tasks_completed_prefix = "${tasks_completed}"
            tasks_completed_field: str = dspy.InputField(
                prefix=tasks_completed_prefix, desc=tasks_completed_desc
            )
            extended_signature = extended_signature.append(
                name="tasks_completed", field=tasks_completed_field, type_=str
            )

        # -- Message Update Output --
        if message_update:
            message_update_desc = (
                "Continue your current message to the user "
                "(latest assistant field in conversation history) with ONE concise sentence that: "
                "- Describes NEW technical details about your latest action "
                "- Highlights specific parameters or logic you just applied "
                "- Avoids repeating anything from conversation history "
                "- Speaks directly to them (no 'the user'), gender neutral message "
                "Just provide the new sentence update, not the full message from the conversation history."
            )

            message_update_prefix = "${message_update}"
            message_update_field: str = dspy.OutputField(
                prefix=message_update_prefix, desc=message_update_desc
            )
            extended_signature = extended_signature.append(
                name="message_update", field=message_update_field, type_=str
            )

        # -- Predict --
        self.predict = dspy.Predict(extended_signature, **config)

    def forward(self, **kwargs):

        # Add the tree data inputs to the kwargs
        kwargs["user_prompt"] = self.tree_data.user_prompt
        kwargs["conversation_history"] = self.tree_data.conversation_history
        kwargs["atlas"] = self.tree_data.atlas

        # Add the optional inputs to the kwargs
        if self.environment:
            kwargs["environment"] = self.tree_data.environment.to_json()

        if self.collection_schemas:
            if self.collection_names != []:
                kwargs["collection_schemas"] = (
                    self.tree_data.output_collection_metadata(
                        collection_names=self.collection_names, with_mappings=False
                    )
                )
            else:
                kwargs["collection_schemas"] = (
                    self.tree_data.output_collection_metadata(with_mappings=False)
                )

        if self.tasks_completed:
            kwargs["tasks_completed"] = self.tree_data.tasks_completed_string()

        return self.predict(**kwargs)

    async def aforward(self, **kwargs):

        # Add the tree data inputs to the kwargs
        kwargs["user_prompt"] = self.tree_data.user_prompt
        kwargs["conversation_history"] = self.tree_data.conversation_history
        kwargs["atlas"] = self.tree_data.atlas

        # Add the optional inputs to the kwargs
        if self.environment:
            kwargs["environment"] = self.tree_data.environment.to_json()

        if self.collection_schemas:
            if self.collection_names != []:
                kwargs["collection_schemas"] = (
                    self.tree_data.output_collection_metadata(
                        collection_names=self.collection_names, with_mappings=False
                    )
                )
            else:
                kwargs["collection_schemas"] = (
                    self.tree_data.output_collection_metadata(with_mappings=False)
                )

        if self.tasks_completed:
            kwargs["tasks_completed"] = self.tree_data.tasks_completed_string()

        return await self.predict.acall(**kwargs)
