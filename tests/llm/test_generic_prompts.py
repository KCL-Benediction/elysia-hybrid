"""
Test generic prompts and basic outputs.
Such as whether a prompt that requires searching actually does call 'query'.
Same for aggregate, text_response, summarise, itemised_summaries.
"""

import json
import pytest
from copy import deepcopy
from deepeval import evaluate, metrics
from deepeval.test_case import LLMTestCase, ToolCall

from elysia import Tree, Settings
from elysia import configure

configure(logging_level="DEBUG")


class TestGenericPrompts:
    base_tree = Tree(
        low_memory=False,
        branch_initialisation="one_branch",
        settings=Settings.from_smart_setup(),
    )

    def get_tools_called(self, tree: Tree, user_prompt: str):
        tools_called = []
        if user_prompt in tree.actions_called:
            for action in tree.actions_called[user_prompt]:
                if action["name"] in tree.tools:
                    tools_called.append(
                        ToolCall(
                            name=action["name"],
                            description=tree.tools[action["name"]].description,
                            input_parameters=action["inputs"],
                            output=action["output"] if "output" in action else [],
                        )
                    )
        return tools_called

    async def run_tree(self, user_prompt: str, collection_names: list[str]):

        tree = deepcopy(self.base_tree)

        async for result in tree.async_run(
            user_prompt,
            collection_names=collection_names,
        ):
            pass
        return tree

    @pytest.mark.asyncio
    async def test_query(self):
        """
        Test the query tool is called for a generic prompt requiring it.
        """
        user_prompt = "What github issues discuss the 'PDF upload' issue?"
        tree = await self.run_tree(
            user_prompt,
            [],
        )

        collection_names_to_test = [c.lower() for c in tree.tree_data.collection_names]

        # passing empty collection list should mean all collections are searched
        assert "example_verba_github_issues" in collection_names_to_test
        assert "example_verba_email_chains" in collection_names_to_test
        assert "example_verba_slack_conversations" in collection_names_to_test
        assert "weather" in collection_names_to_test
        assert "ml_wikipedia" in collection_names_to_test
        assert "weaviate_blogs" in collection_names_to_test
        assert "weaviate_documentation" in collection_names_to_test

        all_decision_history = []
        for iteration in tree.decision_history:
            all_decision_history.extend(iteration)
        assert "query" in all_decision_history

        deepeval_metric = metrics.TaskCompletionMetric(
            threshold=0.5, model="gpt-4o-mini", include_reason=True
        )

        tools_called = self.get_tools_called(tree, user_prompt)

        test_case = LLMTestCase(
            input=user_prompt,
            actual_output=tree.tree_data.conversation_history[-1]["content"],
            tools_called=tools_called,
        )

        res = evaluate(test_cases=[test_case], metrics=[deepeval_metric])
        for test_case in res.test_results:
            assert test_case.success

    @pytest.mark.asyncio
    async def test_aggregate(self):
        """
        Test the aggregate tool is called for a generic prompt requiring it.
        """
        user_prompt = (
            "What is the average price of trousers in the ecommerce collection?"
        )
        tree = await self.run_tree(
            user_prompt,
            [
                "Products",
                "Example_verba_email_chains",
                "Example_verba_github_issues",
                "Example_verba_slack_conversations",
                "Weather",
                "ML_Wikipedia",
                "Weaviate_blogs",
                "Weaviate_documentation",
            ],
        )

        all_decision_history = []
        for iteration in tree.decision_history:
            all_decision_history.extend(iteration)
        assert "aggregate" in all_decision_history

        # Test with deepeval
        deepeval_metric = metrics.TaskCompletionMetric(
            threshold=0.5, model="gpt-4o-mini", include_reason=True
        )

        tools_called = self.get_tools_called(tree, user_prompt)

        test_case = LLMTestCase(
            input=user_prompt,
            actual_output=tree.tree_data.conversation_history[-1]["content"],
            tools_called=tools_called,
        )

        res = evaluate(test_cases=[test_case], metrics=[deepeval_metric])
        for test_case in res.test_results:
            assert test_case.success, test_case.metrics_data[0].reason

    @pytest.mark.asyncio
    async def test_text_response(self):
        """
        Test the text_response tool is called for a generic conversational prompt.
        """
        user_prompt = "Hey Elly what's up? What can you do?"
        tree = await self.run_tree(
            user_prompt,
            [
                "Ecommerce",
                "Example_verba_email_chains",
                "Example_verba_github_issues",
                "Example_verba_slack_conversations",
                "Weather",
                "ML_Wikipedia",
                "Weaviate_blogs",
                "Weaviate_documentation",
            ],
        )

        all_decision_history = []
        for iteration in tree.decision_history:
            all_decision_history.extend(iteration)
        assert "text_response" in all_decision_history

        # Test with deepeval
        deepeval_metric = metrics.TaskCompletionMetric(
            threshold=0.5, model="gpt-4o-mini", include_reason=True
        )

        tools_called = self.get_tools_called(tree, user_prompt)

        test_case = LLMTestCase(
            input=user_prompt,
            actual_output=tree.tree_data.conversation_history[-1]["content"],
            tools_called=tools_called,
        )

        res = evaluate(test_cases=[test_case], metrics=[deepeval_metric])
        for test_case in res.test_results:
            assert test_case.success, test_case.metrics_data[0].reason

    @pytest.mark.asyncio
    async def test_summarising_output(self):
        """
        Test the summarise tool is called for a generic prompt requiring it.
        """
        user_prompt = (
            "Summarise the 10 most recent issues in the github issues collection"
        )
        tree = await self.run_tree(
            user_prompt,
            [
                "Example_verba_github_issues",
            ],
        )

        all_decision_history = []
        for iteration in tree.decision_history:
            all_decision_history.extend(iteration)
        assert "query" in all_decision_history

        env_key = (
            "query_postprocessing"
            if "query_postprocessing" in tree.tree_data.environment.environment
            else "query"
        )

        assert (
            "Example_verba_github_issues"
            in tree.tree_data.environment.environment[env_key]
        )
        assert (
            "cited_summarize" in all_decision_history
            or all_decision_history[-1] == "text_response"
        )

        task_metric = metrics.TaskCompletionMetric(
            threshold=0.5, model="gpt-4o-mini", include_reason=True
        )

        tools_called = self.get_tools_called(tree, user_prompt)

        task_test_case = LLMTestCase(
            input=user_prompt,
            actual_output=tree.tree_data.conversation_history[-1]["content"],
            tools_called=tools_called,
        )

        res = evaluate(test_cases=[task_test_case], metrics=[task_metric])
        for test_case in res.test_results:
            assert test_case.success

        environment = [
            json.dumps(obj)
            for obj in tree.tree_data.environment.environment[env_key][
                "Example_verba_github_issues"
            ][0]["objects"]
        ]

        summarisation_metric = metrics.AnswerRelevancyMetric(
            threshold=0.5, model="gpt-4o", include_reason=True
        )
        summarisation_test_case = LLMTestCase(
            input=user_prompt,
            actual_output=tree.tree_data.conversation_history[-1]["content"],
            retrieval_context=environment,
        )

        res = evaluate(
            test_cases=[summarisation_test_case], metrics=[summarisation_metric]
        )
        for test_case in res.test_results:
            assert test_case.success, test_case.metrics_data[0].reason

    @pytest.mark.asyncio
    async def test_itemised_summaries(self):
        """
        Test the itemised_summaries tool is called when specifically asked for it.
        """
        user_prompt = (
            "Write itemised summaries for each of the 5 most recent message in slack"
        )
        tree = await self.run_tree(
            user_prompt,
            [
                "Example_verba_slack_conversations",
                "Example_verba_email_chains",
                "Example_verba_github_issues",
            ],
        )

        all_decision_history = []
        for iteration in tree.decision_history:
            all_decision_history.extend(iteration)
        assert "query" in all_decision_history
        assert (
            "Example_verba_slack_conversations"
            in tree.tree_data.environment.environment["query_postprocessing"]
        )
        for item in tree.tree_data.environment.environment["query_postprocessing"][
            "Example_verba_slack_conversations"
        ][0]["objects"]:
            assert "ELYSIA_SUMMARY" in item.keys() and len(item["ELYSIA_SUMMARY"]) > 0


# if __name__ == "__main__":
#     import asyncio

#     asyncio.run(TestGenericPrompts().test_itemised_summaries())
