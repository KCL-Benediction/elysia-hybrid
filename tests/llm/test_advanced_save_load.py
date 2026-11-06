from elysia.tree.tree import Tree
from elysia.tree.util import get_saved_trees_weaviate
from elysia.util.client import ClientManager
from elysia.config import Settings

import pytest

from deepeval import evaluate, metrics
from deepeval.test_case import LLMTestCase, LLMTestCaseParams


@pytest.mark.asyncio
async def test_save_load_weaviate():

    client_manager = ClientManager()

    try:
        settings = Settings.from_smart_setup()
        tree = Tree(settings=settings)

        # ask about edward
        tree(
            "What was edward's most recent slack message?",
            collection_names=[
                "Example_verba_slack_conversations",
                "Example_verba_email_chains",
            ],
        )

        # save the tree to weaviate
        await tree.export_to_weaviate(
            collection_name="test_save_load_collection_llm",
            client_manager=client_manager,
        )

        # load the tree from weaviate
        loaded_tree = await Tree.import_from_weaviate(
            collection_name="test_save_load_collection_llm",
            conversation_id=tree.conversation_id,
            client_manager=client_manager,
        )

        assert tree.user_id == loaded_tree.user_id
        assert tree.conversation_id == loaded_tree.conversation_id
        assert (
            loaded_tree.tree_data.conversation_history
            == tree.tree_data.conversation_history
        )

        # now ask about his email without referring to 'edward'
        response, objects = loaded_tree("what about his most recent email?")

        # check that the output includes emails from edward
        # Use a more appropriate metric for the test: check that the response references Edward's email.
        metric = metrics.GEval(
            name="Check Edward's email is referenced",
            criteria="The response should reference Edward's most recent email. The answer should be about Edward's email, not someone else's, and should not hallucinate information if not present.",
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.RETRIEVAL_CONTEXT,
            ],
        )

        test_case = LLMTestCase(
            input="what about his most recent email?",
            actual_output=response,
            expected_output="""
            There should be a response about EDWARD's emails.
            Ensure that the response talks about Edward's most recent email.
            You are only testing if the author of the retrieved email is Edward.
            """,
            retrieval_context=[str(obj) for obj in objects],
        )

        res = evaluate(test_cases=[test_case], metrics=[metric])
        for test_case in res.test_results:
            assert test_case.success

    finally:
        if client_manager.client.collections.exists("test_save_load_collection"):
            await client_manager.client.collections.delete("test_save_load_collection")

        await client_manager.close_clients()
