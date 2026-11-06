from elysia.tree.tree import Tree
from elysia.tree.util import get_saved_trees_weaviate

from elysia.util.client import ClientManager

import pytest


def test_save_load_local():

    tree = Tree(
        user_id="test_save_load_user",
        conversation_id="test_save_load_conversation",
        low_memory=True,
        style="This is a test style!",
        agent_description="This is a test agent description!",
        end_goal="This is a test end goal!",
    )
    tree.tree_data.environment.hidden_environment["Example Entry"] = (
        "This is an example!"
    )

    # save the tree to a file
    tree_json = tree.export_to_json()

    # load the tree from the file
    loaded_tree = Tree.import_from_json(tree_json)

    assert tree.user_id == loaded_tree.user_id
    assert tree.conversation_id == loaded_tree.conversation_id
    assert tree.low_memory == loaded_tree.low_memory
    assert tree.tree_data.atlas.style == loaded_tree.tree_data.atlas.style
    assert (
        tree.tree_data.atlas.agent_description
        == loaded_tree.tree_data.atlas.agent_description
    )
    assert tree.tree_data.atlas.end_goal == loaded_tree.tree_data.atlas.end_goal
    assert "Example Entry" in loaded_tree.tree_data.environment.hidden_environment
    assert (
        tree.tree_data.environment.hidden_environment["Example Entry"]
        == loaded_tree.tree_data.environment.hidden_environment["Example Entry"]
    )


@pytest.mark.asyncio
async def test_save_load_weaviate():

    try:
        tree = Tree(
            user_id="test_save_load_user",
            conversation_id="test_save_load_conversation",
            low_memory=True,
            style="This is a test style!",
            agent_description="This is a test agent description!",
            end_goal="This is a test end goal!",
        )
        tree.tree_data.environment.hidden_environment["Example Entry"] = (
            "This is an example!"
        )

        client_manager = ClientManager()

        # save the tree to weaviate
        await tree.export_to_weaviate(
            collection_name="test_save_load_collection", client_manager=client_manager
        )

        # load the tree from weaviate
        loaded_tree = await Tree.import_from_weaviate(
            collection_name="test_save_load_collection",
            conversation_id=tree.conversation_id,
            client_manager=client_manager,
        )

        assert tree.user_id == loaded_tree.user_id
        assert tree.conversation_id == loaded_tree.conversation_id
        assert tree.low_memory == loaded_tree.low_memory
        assert tree.tree_data.atlas.style == loaded_tree.tree_data.atlas.style
        assert (
            tree.tree_data.atlas.agent_description
            == loaded_tree.tree_data.atlas.agent_description
        )
        assert tree.tree_data.atlas.end_goal == loaded_tree.tree_data.atlas.end_goal
        assert "Example Entry" in loaded_tree.tree_data.environment.hidden_environment
        assert (
            tree.tree_data.environment.hidden_environment["Example Entry"]
            == loaded_tree.tree_data.environment.hidden_environment["Example Entry"]
        )

        saved_trees = await get_saved_trees_weaviate(
            collection_name="test_save_load_collection",
            client_manager=client_manager,
        )

        assert tree.conversation_id in saved_trees

    finally:
        if client_manager.client.collections.exists("test_save_load_collection"):
            client_manager.client.collections.delete("test_save_load_collection")

        await client_manager.close_clients()
