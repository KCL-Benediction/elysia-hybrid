import pytest
import os
import dotenv

from elysia.api.services.user import UserManager
from elysia.api.services.tree import TreeManager
from elysia.config import Settings
from elysia.api.utils.config import Config

dotenv.load_dotenv(override=True)


class TestUserManager:

    @pytest.mark.asyncio
    async def test_user_manager(self):
        user_id = "test_user"
        conversation_id = "test_conversation"

        user_manager = UserManager()

        # will raise error if no user created
        with pytest.raises(ValueError):
            await user_manager.get_user_local(user_id)

        # add a user
        await user_manager.add_user_local(user_id)

        # get user
        user = await user_manager.get_user_local(user_id)
        assert user is not None

        # will raise error if no tree created
        with pytest.raises(ValueError):
            await user_manager.get_tree(user_id, conversation_id)

        # add a tree
        await user_manager.initialise_tree(user_id, conversation_id, low_memory=True)

        # get tree
        tree = await user_manager.get_tree(user_id, conversation_id)
        assert tree is not None

    @pytest.mark.asyncio
    async def test_tree_manager(self):
        user_id = "test_user_tree"
        conversation_id = "test_conversation_tree"

        tree_manager = TreeManager(user_id)

        # will raise error if no tree created
        with pytest.raises(ValueError):
            tree_manager.get_tree(conversation_id)

        # add a tree
        tree_manager.add_tree(conversation_id, low_memory=True)

        # get tree
        tree = tree_manager.get_tree(conversation_id)
        assert tree is not None

    @pytest.mark.asyncio
    async def test_config_in_managers(self):
        user_id = "test_user_config"
        conversation_id = "test_conversation_config"

        user_manager = UserManager()

        # add a tree manager to the user manager without a settings
        await user_manager.add_user_local(user_id)

        # add a tree to the user manager
        await user_manager.initialise_tree(user_id, conversation_id, low_memory=True)

        # get tree manager
        tree_manager = user_manager.users[user_id]["tree_manager"]

        # check that settings is equal to environment variables
        assert tree_manager.settings.API_KEYS["openai_api_key"] == os.environ.get(
            "OPENAI_API_KEY"
        )
        assert tree_manager.settings.WCD_URL == os.environ.get("WCD_URL")
        assert tree_manager.settings.WCD_API_KEY == os.environ.get("WCD_API_KEY")

        # check that the tree has these settings too
        tree = await user_manager.get_tree(user_id, conversation_id)
        assert tree.settings.API_KEYS["openai_api_key"] == os.environ.get(
            "OPENAI_API_KEY"
        )
        assert tree.settings.WCD_URL == os.environ.get("WCD_URL")
        assert tree.settings.WCD_API_KEY == os.environ.get("WCD_API_KEY")

        # create a new user with a new config
        user_id_2 = "test_user_config_2"
        conversation_id_2 = "test_conversation_config_2"

        new_settings = Settings()
        new_settings.configure(
            openai_api_key="new_openai_api_key",
            wcd_url=os.getenv("WCD_URL"),
            wcd_api_key=os.getenv("WCD_API_KEY"),
            base_model="gpt-4o-mini",
            base_provider="openai",
            complex_model="gpt-4o",
            complex_provider="openai",
        )

        await user_manager.add_user_local(
            user_id_2,
            config=Config(
                id="new_config",
                name="New Config",
                settings=new_settings,
                style="Informative, polite and friendly.",
                agent_description="You search and query Weaviate to satisfy the user's query, providing a concise summary of the results.",
                end_goal=(
                    "You have satisfied the user's query, and provided a concise summary of the results. "
                    "Or, you have exhausted all options available, or asked the user for clarification."
                ),
                branch_initialisation="one_branch",
            ),
        )
        await user_manager.initialise_tree(
            user_id_2, conversation_id_2, low_memory=True
        )

        # get tree manager
        tree_manager_2 = user_manager.users[user_id_2]["tree_manager"]

        # check that settings is equal to new settings
        assert (
            tree_manager_2.settings.API_KEYS["openai_api_key"] == "new_openai_api_key"
        )
        assert tree_manager_2.settings.WCD_URL == os.getenv("WCD_URL")
        assert tree_manager_2.settings.WCD_API_KEY == os.getenv("WCD_API_KEY")

        # check that the tree has these settings too
        tree_2 = await user_manager.get_tree(user_id_2, conversation_id_2)
        assert tree_2.settings.API_KEYS["openai_api_key"] == "new_openai_api_key"
        assert tree_2.settings.WCD_URL == os.getenv("WCD_URL")
        assert tree_2.settings.WCD_API_KEY == os.getenv("WCD_API_KEY")
