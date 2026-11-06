from typing import Literal

import dspy

from elysia.tree.objects import Atlas


def construct_decision_prompt(
    available_tasks: list[str] | None = None,
) -> dspy.Signature:
    ActionLiteral = (
        Literal[tuple(available_tasks)]
        if (available_tasks is not None and len(available_tasks) > 0)  # type: ignore
        else str
    )

    class DecisionPrompt(dspy.Signature):
        """
        You are a routing agent within Elysia, named Elly (short for Elysia), responsible for selecting the most appropriate next task to handle a user's input.
        Your goal is to ensure the user receives a complete and accurate response through a series of task selections.
        You also respond to the user.

        Core Decision Process:
        1. Analyze the user's input prompt and available tasks
        2. Review completed tasks and their outcomes in previous_reasoning
        3. Check if current information satisfies the input prompt
        4. Select the most appropriate next task from available_tasks
        5. Determine if all possible actions have been exhausted

        Decision Rules:
        - Always select from available_tasks list only
        - Prefer tasks that directly progress toward answering the input prompt
        - Consider tree_count to avoid repetitive decisions
        """

        # Regular input fields
        instruction: str = dspy.InputField(
            description="Specific guidance for this decision point that must be followed"
        )

        tree_count: str = dspy.InputField(
            description="""
            Current attempt number as "X/Y" where:
            - X = current attempt number
            - Y = maximum allowed attempts
            Consider ending the process as X approaches Y.
            """.strip()
        )

        # Task-specific input fields
        available_actions: list[dict] = dspy.InputField(
            description="""
            List of possible actions to choose from:
            {
                "[name]": {
                    "function_name": [name of the function],
                    "description": [task description],
                    "future": [future information],
                    "inputs": [inputs for the action]. A dictionary where the keys are the input names, and the values are the input descriptions.
                }
            }
            """.strip()
        )

        function_name: ActionLiteral = dspy.OutputField(
            description="""
            Select exactly one function name from available_actions that best advances toward answering the user's input prompt.
            You MUST select one function name exactly as written as it appears in the `function_name` field of the dictionary.
            You can select a function again in the future if you need to, you are allowed to choose the same function multiple times.
            If unsure, you should try to complete an action that is related to the user prompt, even if it looks hard. However, do not continually choose the same action.
            """.strip()
        )

        function_inputs: dict = dspy.OutputField(
            description="""
            The inputs for the action/function you have selected. These must match exactly the inputs shown for the action you have selected.
            If it does not, the code will error.
            Choose based on the user prompt and the environment.
            The keys of this should match exactly the keys of `available_actions[function_name]["inputs"]`.
            Return an empty dict ({}) if there are no inputs (and `available_actions[function_name]["inputs"] = {}`).
            """.strip(),
            format=dict,
        )

        end_actions: bool = dspy.OutputField(
            description="""
            Has the `end_goal` been achieved?
            Indicates whether to cease actions _after_ completing the selected task.
            Determine this based on the completion of all possible actions for the prompt and the `end_goal`.
            Set to True if you intend to wait for user input, as failing to do so will result in continued responses.
            Even if not all actions can be completed, you should stop if you have done everything possible.
            """.strip()
        )

    return DecisionPrompt


class FollowUpSuggestionsPrompt(dspy.Signature):
    """
    Expert at suggesting engaging follow-up questions based on recent user interactions.
    Generate questions that showcase system capabilities and maintain user interest.
    Questions should be fun, creative, and designed to impress.

    System context:
    An agentic RAG service querying or aggregating information from Weaviate collections via filtering, sorting, multi-collection queries, summary statistics.
    Uses tree-based approach with specialized agents and decision nodes for dynamic information retrieval,
    summary generation, and real-time results display while maintaining natural conversation flow.

    Since you are suggesting _follow-up_ questions, you should not suggest questions that are too similar to the user's prompt.
    Instead, try to think of something that can connect different data sources together, or provide new insights that the user may not have thought of.
    These should be fully formed questions, that you think the system is capable of answering, that the user would be interested in, and that show off the system's capabilities.

    Use `data_information` to see if there are cross-overs between the already retrieved data (environment) and any other data sources.
    It is important you study these in depth so you do not create follow-up questions that would be impossible or very difficult to answer.

    Do not suggest questions that will require _complex_ calculations or reasoning, it should be mostly focused on following up on the already retrieved data,
    or following up by retrieving similar or new data that is related to the already retrieved data.
    """

    user_prompt = dspy.InputField(description="The user's input prompt.")
    reference: dict = dspy.InputField(
        desc="""
        Current state information like date/time to frame.
        """.strip(),
        format=str,
    )
    conversation_history: list[dict] = dspy.InputField(
        description="""
        Full conversation history between user and assistant, including generated information in environment field.
        Format: [{"role": "user"/"assistant", "content": message}]
        Use as context for future responses if non-empty.
        """.strip(),
        format=str,
    )
    environment: str = dspy.InputField(
        description="Information gathered from completed tasks. These are already shown to the user. Use for context, and to cross reference with data_information.",
        format=str,
    )
    data_information: dict = dspy.InputField(
        desc="""
        Collection metadata to inform query choices. Format per collection:
        {
            "name": data collection name,
            "length": object count,
            "summary": collection summary,
            "fields": {
                "field_name": {
                    "groups": unique text values (empty if non-text),
                    "mean": average field length (tokens/list items),
                    "range": min/max length values,
                    "type": data type
                }
            }
        }
        Use this to see if there are cross-overs between the currently retrieved data (environment) and any other collections, to help make an interesting question.
        Also use this to NOT suggest questions that would be impossible.
        This is IMPORTANT. Do not suggest questions that would be impossible, i.e., you can see the distinct categories between the collections, and look for overlap between the environment and these groups.
        If you can't find any overlap, do not assume there is any.
        Instead, suggest a question that would be a generic follow-up based on the environment/prompt.
        But if you do see overlap, suggest a question that would be a follow-up based on the overlap!
        """.strip(),
        format=str,
    )
    old_suggestions: list[str] = dspy.InputField(
        description="A list of questions that have already been suggested. Do not suggest the same question (or anything similar) as any items in this list.",
        format=str,
    )
    suggestions: list[str] = dspy.OutputField(
        description="A list of follow up questions to the user's prompt. Around 2 questions. These should be punctual, short, around 10 words or so. Try to mix up the vocabulary and type of question between them."
    )
