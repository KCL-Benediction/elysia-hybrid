import os
from fastapi.responses import JSONResponse

import json
import random
import pytest
from elysia.api.api_types import (
    ListConfigsData,
    LoadConfigUserData,
    LoadConfigTreeData,
    SaveConfigData,
    ChangeConfigUserData,
    ChangeConfigTreeData,
    DefaultModelsUserData,
    DefaultModelsTreeData,
    EnvironmentSettingsUserData,
    InitialiseUserData,
    InitialiseTreeData,
    Config,
)
from elysia.api.dependencies.common import get_user_manager
from elysia.api.routes.init import initialise_tree, initialise_user
from elysia.api.routes.config import (
    save_config,
    load_config_tree,
    load_config_user,
    change_config_tree,
    change_config_user,
    default_models_user,
    default_models_tree,
    environment_settings_user,
    list_configs,
)
from elysia.tree.tree import Tree
from elysia.api.core.log import logger, set_log_level
from elysia.api.services.tree import TreeManager

set_log_level("CRITICAL")


def read_response(response: JSONResponse):
    return json.loads(response.body)


class TestConfig:
    user_manager = get_user_manager()

    @pytest.mark.asyncio
    async def test_initialise_user_default_models(self):

        try:
            user_id = "test_user_initialise_user_default_models"
            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id,
                    default_models=True,
                ),
                user_manager=self.user_manager,
            )

            response = read_response(response)
            assert response["error"] == ""

            # check that the tree manager has the correct settings
            tree_manager = self.user_manager.users[user_id]["tree_manager"]

            assert tree_manager.settings.BASE_MODEL == os.getenv(
                "BASE_MODEL", "gemini-2.0-flash-001"
            )
            assert tree_manager.settings.COMPLEX_MODEL == os.getenv(
                "COMPLEX_MODEL", "gemini-2.0-flash-001"
            )
            assert tree_manager.settings.BASE_PROVIDER == os.getenv(
                "BASE_PROVIDER", "openrouter/google"
            )
            assert tree_manager.settings.COMPLEX_PROVIDER == os.getenv(
                "COMPLEX_PROVIDER", "openrouter/google"
            )

            # should default use environment variables
            assert response["config"]["settings"]["WCD_URL"] == os.getenv("WCD_URL")
            assert response["config"]["settings"]["WCD_API_KEY"] == os.getenv(
                "WCD_API_KEY"
            )
            assert response["config"]["style"] != ""
            assert response["config"]["agent_description"] != ""
            assert response["config"]["end_goal"] != ""
            assert response["config"]["branch_initialisation"] != ""

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_initialise_user_custom_models(self):

        try:
            user_id = "test_user_initialise_user_custom_models"
            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id,
                    default_models=False,
                    settings={
                        "BASE_MODEL": "gpt-4o-mini",
                        "COMPLEX_MODEL": "gpt-4o",
                        "BASE_PROVIDER": "openai",
                        "COMPLEX_PROVIDER": "openai",
                        "OPENAI_API_KEY": "test_openai_key",
                        "WCD_URL": "test_wcd_url",
                    },
                ),
                user_manager=self.user_manager,
            )

            response = read_response(response)
            assert response["error"] == ""

            # check that the tree manager has the correct settings
            tree_manager = self.user_manager.users[user_id]["tree_manager"]

            assert tree_manager.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree_manager.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree_manager.settings.BASE_PROVIDER == "openai"
            assert tree_manager.settings.COMPLEX_PROVIDER == "openai"

            # configs returned should match the settings provided
            assert response["config"]["settings"]["BASE_MODEL"] == "gpt-4o-mini"
            assert response["config"]["settings"]["COMPLEX_MODEL"] == "gpt-4o"
            assert response["config"]["settings"]["BASE_PROVIDER"] == "openai"
            assert response["config"]["settings"]["COMPLEX_PROVIDER"] == "openai"
            assert (
                response["config"]["settings"]["API_KEYS"]["openai_api_key"]
                == "test_openai_key"
            )
            assert response["config"]["settings"]["WCD_URL"] == "test_wcd_url"

            # api keys that are not set should come from environment variables
            assert response["config"]["settings"]["WCD_API_KEY"] == os.getenv(
                "WCD_API_KEY"
            )

            # style, agent_description and end_goal should be set
            assert response["config"]["style"] != ""
            assert response["config"]["agent_description"] != ""
            assert response["config"]["end_goal"] != ""
            assert response["config"]["branch_initialisation"] != ""

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_default_models_user(self):
        try:
            user_id = "test_user_default_models_user"

            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id,
                    default_models=False,
                ),
                user_manager=self.user_manager,
            )

            response = await default_models_user(
                data=DefaultModelsUserData(
                    user_id=user_id,
                ),
                user_manager=self.user_manager,
            )

            response = read_response(response)
            assert response["error"] == ""

            # check that the tree manager has the correct settings
            tree_manager = self.user_manager.users[user_id]["tree_manager"]

            assert tree_manager.settings.BASE_MODEL == os.getenv(
                "BASE_MODEL", "gemini-2.0-flash-001"
            )
            assert tree_manager.settings.COMPLEX_MODEL == os.getenv(
                "COMPLEX_MODEL", "gemini-2.0-flash-001"
            )
            assert tree_manager.settings.BASE_PROVIDER == os.getenv(
                "BASE_PROVIDER", "openrouter/google"
            )
            assert tree_manager.settings.COMPLEX_PROVIDER == os.getenv(
                "COMPLEX_PROVIDER", "openrouter/google"
            )

            # should default use environment variables
            assert response["config"]["settings"]["WCD_URL"] == os.getenv("WCD_URL")
            assert response["config"]["settings"]["WCD_API_KEY"] == os.getenv(
                "WCD_API_KEY"
            )
            assert response["config"]["style"] != ""
            assert response["config"]["agent_description"] != ""
            assert response["config"]["end_goal"] != ""
            assert response["config"]["branch_initialisation"] != ""

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_default_models_tree(self):
        try:
            user_id = "test_user_default_models_tree"
            conversation_id = "test_conversation_default_models_tree"

            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id,
                    default_models=False,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)

            assert response["error"] == ""

            # should be no models set yet
            tree_manager = self.user_manager.users[user_id]["tree_manager"]
            assert tree_manager.settings.BASE_MODEL is None
            assert tree_manager.settings.COMPLEX_MODEL is None
            assert tree_manager.settings.BASE_PROVIDER is None
            assert tree_manager.settings.COMPLEX_PROVIDER is None

            # set the models
            response = await initialise_tree(
                data=InitialiseTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    low_memory=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # should be no models in the tree
            tree: Tree = await self.user_manager.get_tree(user_id, conversation_id)
            assert tree.settings.BASE_MODEL is None
            assert tree.settings.COMPLEX_MODEL is None
            assert tree.settings.BASE_PROVIDER is None
            assert tree.settings.COMPLEX_PROVIDER is None

            # set the models
            response = await default_models_tree(
                data=DefaultModelsTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # check that the tree manager hasn't changed
            tree_manager = self.user_manager.users[user_id]["tree_manager"]

            assert tree_manager.settings.BASE_MODEL is None
            assert tree_manager.settings.COMPLEX_MODEL is None
            assert tree_manager.settings.BASE_PROVIDER is None
            assert tree_manager.settings.COMPLEX_PROVIDER is None

            # and the tree should have the correct models
            assert tree.settings.BASE_MODEL == os.getenv(
                "BASE_MODEL", "gemini-2.0-flash-001"
            )
            assert tree.settings.COMPLEX_MODEL == os.getenv(
                "COMPLEX_MODEL", "gemini-2.0-flash-001"
            )
            assert tree.settings.BASE_PROVIDER == os.getenv(
                "BASE_PROVIDER", "openrouter/google"
            )
            assert tree.settings.COMPLEX_PROVIDER == os.getenv(
                "COMPLEX_PROVIDER", "openrouter/google"
            )
        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_environment_settings_user(self):
        try:
            user_id = "test_user_environment_settings"

            # Setup: Initialize user with empty settings
            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id,
                    default_models=False,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Exercise: Apply environment settings
            response = await environment_settings_user(
                data=EnvironmentSettingsUserData(
                    user_id=user_id,
                ),
                user_manager=self.user_manager,
            )

            # Verify response is OK
            response = read_response(response)
            assert response["error"] == ""

            # Verify settings were updated from environment
            user = await self.user_manager.get_user_local(user_id)
            tree_manager = user["tree_manager"]

            # Check API keys were loaded from environment
            assert tree_manager.settings.WCD_URL == os.getenv("WCD_URL", "")
            assert tree_manager.settings.WCD_API_KEY == os.getenv("WCD_API_KEY", "")

            # Verify client manager API keys were updated
            client_manager = user["client_manager"]
            assert client_manager.wcd_api_key == os.getenv("WCD_API_KEY", "")

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_change_config_user(self):
        try:
            user_id = "test_user_change_config_user"

            # Setup: Initialize user with default settings
            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id,
                    default_models=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Create a tree to verify changes propagate
            conversation_id = "test_conversation_change_config_user"
            response = await initialise_tree(
                data=InitialiseTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    low_memory=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Exercise: Change user config
            new_settings = {
                "BASE_MODEL": "gpt-4o-mini",
                "COMPLEX_MODEL": "gpt-4o",
                "BASE_PROVIDER": "openai",
                "COMPLEX_PROVIDER": "openai",
            }
            new_style = "Professional and concise."
            new_agent_description = "You are a helpful assistant that searches data."
            new_end_goal = "Provide accurate information to the user."
            new_branch_init = "two_branch"

            response = await change_config_user(
                data=ChangeConfigUserData(
                    user_id=user_id,
                    settings=new_settings,
                    style=new_style,
                    agent_description=new_agent_description,
                    end_goal=new_end_goal,
                    branch_initialisation=new_branch_init,
                ),
                user_manager=self.user_manager,
            )

            # Verify response is OK
            response = read_response(response)
            assert response["error"] == ""

            # Verify user settings were updated
            user = await self.user_manager.get_user_local(user_id)
            tree_manager = user["tree_manager"]

            assert tree_manager.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree_manager.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree_manager.settings.BASE_PROVIDER == "openai"
            assert tree_manager.settings.COMPLEX_PROVIDER == "openai"

            assert tree_manager.style == new_style
            assert tree_manager.agent_description == new_agent_description
            assert tree_manager.end_goal == new_end_goal
            assert tree_manager.branch_initialisation == new_branch_init

            # Verify model settings propagated to existing tree
            tree: Tree = await self.user_manager.get_tree(user_id, conversation_id)
            assert tree.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree.settings.BASE_PROVIDER == "openai"
            assert tree.settings.COMPLEX_PROVIDER == "openai"

            # But style, agent_description, etc. should NOT have propagated to existing tree
            assert tree.tree_data.atlas.style != new_style
            assert tree.tree_data.atlas.agent_description != new_agent_description
            assert tree.tree_data.atlas.end_goal != new_end_goal
            assert tree.branch_initialisation != new_branch_init

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_change_config_tree(self):
        try:
            user_id = "test_user_change_config_tree"
            conversation_id = "test_conversation_change_config_tree"

            # Setup: Initialize user and tree
            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id,
                    default_models=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            response = await initialise_tree(
                data=InitialiseTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    low_memory=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # get initial settings
            tree: Tree = await self.user_manager.get_tree(user_id, conversation_id)
            initial_base_model = tree.settings.BASE_MODEL
            initial_style = tree.tree_data.atlas.style

            # change tree config
            new_settings = {
                "BASE_MODEL": "gpt-3.5-turbo",
                "COMPLEX_MODEL": "gpt-4-turbo",
                "BASE_PROVIDER": "openai",
                "COMPLEX_PROVIDER": "openai",
                # Try including API keys, which should be ignored
                "openai_api_key": "test_key_should_be_ignored",
                "wcd_url": "should_be_ignored_too",
            }
            new_style = "Technical and detailed."
            new_agent_description = "You are a technical assistant."
            new_end_goal = "Provide technical details to the user."
            new_branch_init = "empty"

            response = await change_config_tree(
                data=ChangeConfigTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    settings=new_settings,
                    style=new_style,
                    agent_description=new_agent_description,
                    end_goal=new_end_goal,
                    branch_initialisation=new_branch_init,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Tree settings should have been updated
            tree = await self.user_manager.get_tree(user_id, conversation_id)
            assert tree.settings.BASE_MODEL == "gpt-3.5-turbo"
            assert tree.settings.COMPLEX_MODEL == "gpt-4-turbo"
            assert tree.settings.BASE_PROVIDER == "openai"
            assert tree.settings.COMPLEX_PROVIDER == "openai"
            assert tree.tree_data.atlas.style == new_style
            assert tree.tree_data.atlas.agent_description == new_agent_description
            assert tree.tree_data.atlas.end_goal == new_end_goal
            assert tree.branch_initialisation == new_branch_init

            # But not api keys
            assert (
                "openai_api_key" not in tree.settings.to_json()
                or tree.settings.to_json()["openai_api_key"]
                != "test_key_should_be_ignored"
            )
            assert tree.settings.WCD_URL != "should_be_ignored_too"

            # user-level settings should remain unchanged
            user = await self.user_manager.get_user_local(user_id)
            tree_manager = user["tree_manager"]
            assert tree_manager.settings.BASE_MODEL == initial_base_model
            assert tree_manager.style == initial_style

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_config_workflow(self):
        try:
            user_id = "test_user_config_workflow"
            conversation_id_1 = "test_conversation_workflow_1"
            conversation_id_2 = "test_conversation_workflow_2"

            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id,
                    default_models=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Create tree 1 with default settings
            response = await initialise_tree(
                data=InitialiseTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id_1,
                    low_memory=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Test changing config
            user_settings = {
                "BASE_MODEL": "gpt-4o-mini",
                "COMPLEX_MODEL": "gpt-4o",
                "BASE_PROVIDER": "openai",
                "COMPLEX_PROVIDER": "openai",
            }
            response = await change_config_user(
                data=ChangeConfigUserData(
                    user_id=user_id,
                    settings=user_settings,
                    style="Professional style for user",
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Check tree manager settings
            tree_manager = self.user_manager.users[user_id]["tree_manager"]
            assert tree_manager.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree_manager.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree_manager.settings.BASE_PROVIDER == "openai"
            assert tree_manager.settings.COMPLEX_PROVIDER == "openai"

            # Verify tree 1 inherits user model settings but not style
            tree1: Tree = await self.user_manager.get_tree(user_id, conversation_id_1)
            assert tree1.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree1.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree1.tree_data.atlas.style != "Professional style for user"

            # Create tree 2
            response = await initialise_tree(
                data=InitialiseTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id_2,
                    low_memory=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Tree 2 should inherit the new settings
            tree2: Tree = await self.user_manager.get_tree(user_id, conversation_id_2)
            assert tree2.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree2.settings.COMPLEX_MODEL == "gpt-4o"

            # Change tree 1 settings
            tree1_settings = {
                "BASE_MODEL": "claude-3-haiku",
                "COMPLEX_MODEL": "claude-3-opus",
                "BASE_PROVIDER": "anthropic",
                "COMPLEX_PROVIDER": "anthropic",
            }
            response = await change_config_tree(
                data=ChangeConfigTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id_1,
                    settings=tree1_settings,
                    style="Custom tree 1 style",
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Verify tree 1 has its own settings now
            tree1 = await self.user_manager.get_tree(user_id, conversation_id_1)
            assert tree1.settings.BASE_MODEL == "claude-3-haiku"
            assert tree1.settings.COMPLEX_MODEL == "claude-3-opus"
            assert tree1.tree_data.atlas.style == "Custom tree 1 style"

            # change user settings again
            new_user_settings = {
                "BASE_MODEL": "gemini-pro",
                "COMPLEX_MODEL": "gemini-ultra",
                "BASE_PROVIDER": "google",
                "COMPLEX_PROVIDER": "google",
            }
            response = await change_config_user(
                data=ChangeConfigUserData(
                    user_id=user_id,
                    settings=new_user_settings,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Tree 1 should keep its own settings
            tree1 = await self.user_manager.get_tree(user_id, conversation_id_1)
            assert tree1.settings.BASE_MODEL == "claude-3-haiku"
            assert tree1.settings.COMPLEX_MODEL == "claude-3-opus"

            # But tree 2 should inherit updated user settings
            tree2 = await self.user_manager.get_tree(user_id, conversation_id_2)
            assert tree2.settings.BASE_MODEL == "gemini-pro"
            assert tree2.settings.COMPLEX_MODEL == "gemini-ultra"

            # set default models for tree 1
            response = await default_models_tree(
                data=DefaultModelsTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id_1,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # tree 1 should now have default models
            tree1 = await self.user_manager.get_tree(user_id, conversation_id_1)
            assert tree1.settings.BASE_MODEL == os.getenv(
                "BASE_MODEL", "gemini-2.0-flash-001"
            )
            assert tree1.settings.COMPLEX_MODEL == os.getenv(
                "COMPLEX_MODEL", "gemini-2.0-flash-001"
            )
            assert tree1.settings.BASE_PROVIDER == os.getenv(
                "BASE_PROVIDER", "openrouter/google"
            )
            assert tree1.settings.COMPLEX_PROVIDER == os.getenv(
                "COMPLEX_PROVIDER", "openrouter/google"
            )

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_save_config(self):
        try:
            user_id = "test_user_save_config"
            config_id = f"test_config_{random.randint(0, 1000000)}"

            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id,
                    default_models=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # create a config and save
            user = await self.user_manager.get_user_local(user_id)
            tree_manager: TreeManager = user["tree_manager"]

            config = Config(
                settings=tree_manager.settings.to_json(),
                style=tree_manager.style,
                agent_description=tree_manager.agent_description,
                end_goal=tree_manager.end_goal,
                branch_initialisation=tree_manager.branch_initialisation,
                config_id=config_id,
            )

            response = await save_config(
                data=SaveConfigData(
                    user_id=user_id,
                    config_id=config_id,
                    config=config,
                ),
                user_manager=self.user_manager,
            )

            response = read_response(response)
            assert response["error"] == ""

            # verify the config was saved by listing all configs
            response = await list_configs(
                data=ListConfigsData(
                    user_id=user_id,
                ),
                user_manager=self.user_manager,
            )

            response = read_response(response)
            assert response["error"] == ""
            assert config_id in response["configs"]

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_load_config_user(self):
        try:
            user_id = "test_user_load_config_user"
            config_id = f"test_config_user_{random.randint(0, 1000000)}"

            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id,
                    default_models=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # create a config to save with custom settings
            settings = {
                "BASE_MODEL": "gpt-4o-mini",
                "COMPLEX_MODEL": "gpt-4o",
                "BASE_PROVIDER": "openai",
                "COMPLEX_PROVIDER": "openai",
            }
            custom_style = "Technical and precise."
            custom_agent_description = (
                "You are a technical assistant focusing on details."
            )
            custom_end_goal = "Provide technically accurate information to users."
            custom_branch_init = "two_branch"

            config = Config(
                settings=settings,
                style=custom_style,
                agent_description=custom_agent_description,
                end_goal=custom_end_goal,
                branch_initialisation=custom_branch_init,
                config_id=config_id,
            )

            response = await save_config(
                data=SaveConfigData(
                    user_id=user_id,
                    config_id=config_id,
                    config=config,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # change user settings to something different for testing
            response = await change_config_user(
                data=ChangeConfigUserData(
                    user_id=user_id,
                    settings={
                        "BASE_MODEL": "claude-3-haiku",
                        "COMPLEX_MODEL": "claude-3-opus",
                        "BASE_PROVIDER": "anthropic",
                        "COMPLEX_PROVIDER": "anthropic",
                    },
                    style="Conversational and friendly.",
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Load the config back for the user
            response = await load_config_user(
                data=LoadConfigUserData(
                    user_id=user_id,
                    config_id=config_id,
                    include_atlas=True,
                    include_branch_initialisation=True,
                    include_settings=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Check the user settings were updated back to the saved config
            user = await self.user_manager.get_user_local(user_id)
            tree_manager = user["tree_manager"]

            assert tree_manager.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree_manager.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree_manager.settings.BASE_PROVIDER == "openai"
            assert tree_manager.settings.COMPLEX_PROVIDER == "openai"
            assert tree_manager.style == custom_style
            assert tree_manager.agent_description == custom_agent_description
            assert tree_manager.end_goal == custom_end_goal
            assert tree_manager.branch_initialisation == custom_branch_init

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_load_config_tree(self):
        """Test loading a config for a tree from the Weaviate database."""
        try:
            user_id = "test_user_load_config_tree"
            config_id = f"test_config_tree_{random.randint(0, 1000000)}"
            conversation_id = "test_conversation_load_config_tree"

            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id,
                    default_models=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            response = await initialise_tree(
                data=InitialiseTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    low_memory=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Create a config to save
            settings = {
                "BASE_MODEL": "gpt-4-turbo",
                "COMPLEX_MODEL": "gpt-4-vision",
                "BASE_PROVIDER": "openai",
                "COMPLEX_PROVIDER": "openai",
            }
            custom_style = "Analytical and detailed."
            custom_agent_description = (
                "You are an analytical assistant providing detailed analyses."
            )
            custom_end_goal = "Provide thorough and analytical responses to queries."
            custom_branch_init = "empty"

            config = Config(
                settings=settings,
                style=custom_style,
                agent_description=custom_agent_description,
                end_goal=custom_end_goal,
                branch_initialisation=custom_branch_init,
                config_id=config_id,
            )

            response = await save_config(
                data=SaveConfigData(
                    user_id=user_id,
                    config_id=config_id,
                    config=config,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # get initial tree settings to compare later
            tree: Tree = await self.user_manager.get_tree(user_id, conversation_id)
            initial_base_model = tree.settings.BASE_MODEL
            initial_style = tree.tree_data.atlas.style

            # Load the config for the tree (just settings, not atlas or branch init)
            response = await load_config_tree(
                data=LoadConfigTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    config_id=config_id,
                    include_atlas=False,
                    include_branch_initialisation=False,
                    include_settings=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Verify the tree settings were updated but not the atlas or branch init
            tree = await self.user_manager.get_tree(user_id, conversation_id)
            assert tree.settings.BASE_MODEL == "gpt-4-turbo"
            assert tree.settings.COMPLEX_MODEL == "gpt-4-vision"
            assert tree.settings.BASE_PROVIDER == "openai"
            assert tree.settings.COMPLEX_PROVIDER == "openai"

            # Atlas and branch init should not have changed
            assert tree.tree_data.atlas.style != custom_style
            assert tree.branch_initialisation != custom_branch_init

            # Load everything now
            response = await load_config_tree(
                data=LoadConfigTreeData(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    config_id=config_id,
                    include_atlas=True,
                    include_branch_initialisation=True,
                    include_settings=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Verify everything changed
            tree = await self.user_manager.get_tree(user_id, conversation_id)
            assert tree.settings.BASE_MODEL == "gpt-4-turbo"
            assert tree.settings.COMPLEX_MODEL == "gpt-4-vision"
            assert tree.tree_data.atlas.style == custom_style
            assert tree.tree_data.atlas.agent_description == custom_agent_description
            assert tree.tree_data.atlas.end_goal == custom_end_goal
            assert tree.branch_initialisation == custom_branch_init

            # User level settings should remain unchanged
            user = await self.user_manager.get_user_local(user_id)
            tree_manager = user["tree_manager"]
            assert tree_manager.settings.BASE_MODEL == initial_base_model
            assert tree_manager.style == initial_style

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_list_configs(self):
        """Test listing configs from the Weaviate database."""
        try:
            user_id = "test_user_list_configs"
            config_ids = [
                f"test_config_list_{i}_{random.randint(0, 1000000)}" for i in range(3)
            ]

            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id,
                    default_models=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Save multiple configs
            for i, config_id in enumerate(config_ids):
                config = Config(
                    settings={
                        "BASE_MODEL": f"model-{i}",
                        "COMPLEX_MODEL": f"complex-model-{i}",
                        "BASE_PROVIDER": "test-provider",
                        "COMPLEX_PROVIDER": "test-provider",
                    },
                    style=f"Style {i}",
                    agent_description=f"Agent description {i}",
                    end_goal=f"End goal {i}",
                    branch_initialisation="one_branch",
                    config_id=config_id,
                )

                response = await save_config(
                    data=SaveConfigData(
                        user_id=user_id,
                        config_id=config_id,
                        config=config,
                    ),
                    user_manager=self.user_manager,
                )
                response = read_response(response)
                assert response["error"] == ""

            response = await list_configs(
                data=ListConfigsData(
                    user_id=user_id,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            for config_id in config_ids:
                assert config_id in response["configs"]

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_config_save_load_workflow(self):
        """Test a workflow of saving and loading configs between users and trees."""
        try:
            # Setup with unique IDs
            user_id_1 = "test_user_config_workflow_1"
            user_id_2 = "test_user_config_workflow_2"
            conversation_id_1 = "test_conversation_workflow_1"
            conversation_id_2 = "test_conversation_workflow_2"
            config_id = f"test_shared_config_{random.randint(0, 1000000)}"

            # Initialize the first user with custom settings
            custom_settings = {
                "BASE_MODEL": "gpt-4o",
                "COMPLEX_MODEL": "gpt-4o",
                "BASE_PROVIDER": "openai",
                "COMPLEX_PROVIDER": "openai",
            }
            custom_style = "Expert and technical."

            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id_1,
                    default_models=False,
                    settings=custom_settings,
                    style=custom_style,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Create a tree for user 1 using the user-level settings
            response = await initialise_tree(
                data=InitialiseTreeData(
                    user_id=user_id_1,
                    conversation_id=conversation_id_1,
                    low_memory=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Save the config from user 1
            user1 = await self.user_manager.get_user_local(user_id_1)
            tree_manager1: TreeManager = user1["tree_manager"]

            config = Config(
                settings=tree_manager1.settings.to_json(),
                style=tree_manager1.style,
                agent_description=tree_manager1.agent_description,
                end_goal=tree_manager1.end_goal,
                branch_initialisation=tree_manager1.branch_initialisation,
                config_id=config_id,
            )

            response = await save_config(
                data=SaveConfigData(
                    user_id=user_id_1,
                    config_id=config_id,
                    config=config,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Initialize the second user with default models
            response = await initialise_user(
                data=InitialiseUserData(
                    user_id=user_id_2,
                    default_models=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Create a tree for user 2
            response = await initialise_tree(
                data=InitialiseTreeData(
                    user_id=user_id_2,
                    conversation_id=conversation_id_2,
                    low_memory=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # user 2 and tree 2 should have default settings
            user2 = await self.user_manager.get_user_local(user_id_2)
            tree_manager2: TreeManager = user2["tree_manager"]
            assert tree_manager2.settings.BASE_MODEL != "gpt-4o"
            assert tree_manager2.style != custom_style

            tree2: Tree = await self.user_manager.get_tree(user_id_2, conversation_id_2)
            assert tree2.settings.BASE_MODEL != "gpt-4o"

            # Load user 1's config to user 2 (just settings, not atlas) at the user level
            response = await load_config_user(
                data=LoadConfigUserData(
                    user_id=user_id_2,
                    config_id=config_id,
                    include_atlas=False,
                    include_branch_initialisation=False,
                    include_settings=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Now verify user 2 has user 1's settings but not style
            user2 = await self.user_manager.get_user_local(user_id_2)
            tree_manager2: TreeManager = user2["tree_manager"]
            assert tree_manager2.settings.BASE_MODEL == "gpt-4o"
            assert tree_manager2.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree_manager2.style != custom_style

            # Changes to user 2 should propagate to the tree (not used its own settings)
            tree2: Tree = await self.user_manager.get_tree(user_id_2, conversation_id_2)
            assert tree2.settings.BASE_MODEL == "gpt-4o"
            assert tree2.settings.COMPLEX_MODEL == "gpt-4o"

            # Load the config to tree 1 directly (include atlas and settings)
            response = await load_config_tree(
                data=LoadConfigTreeData(
                    user_id=user_id_2,
                    conversation_id=conversation_id_2,
                    config_id=config_id,
                    include_atlas=True,
                    include_branch_initialisation=True,
                    include_settings=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Verify tree 2 now has user 1's style
            tree2 = await self.user_manager.get_tree(user_id_2, conversation_id_2)
            assert tree2.settings.BASE_MODEL == "gpt-4o"
            assert tree2.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree2.tree_data.atlas.style == custom_style

        finally:
            await self.user_manager.close_all_clients()


if __name__ == "__main__":
    import asyncio

    asyncio.run(TestConfig().test_load_config_tree())
