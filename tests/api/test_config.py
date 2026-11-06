import os
from fastapi.responses import JSONResponse
from pathlib import Path
from logging import Logger
import json
import random
import pytest
from weaviate.util import generate_uuid5
from elysia.api.api_types import (
    InitialiseTreeData,
    SaveConfigUserData,
    SaveConfigTreeData,
    UpdateFrontendConfigData,
)
from elysia.api.dependencies.common import get_user_manager
from elysia.api.routes.init import initialise_tree, initialise_user
from elysia.api.routes.user_config import (
    load_config_user,
    delete_config,
    save_config_user,
    new_user_config,
    list_configs,
    update_frontend_config,
    get_models,
)
from elysia.api.routes.tree_config import (
    load_config_tree,
    change_config_tree,
    new_tree_config,
)
from elysia.tree.tree import Tree
from elysia.api.core.log import logger, set_log_level
from elysia.api.services.tree import TreeManager
from elysia.api.services.user import UserManager
from elysia.api.utils.config import FrontendConfig

set_log_level("CRITICAL")


def read_response(response: JSONResponse):
    return json.loads(response.body)


def get_frontend_config_file_path(user_id: str) -> Path:
    elysia_package_dir = Path(__file__).parent.parent.parent  # Gets to elysia/
    config_dir = elysia_package_dir / "elysia" / "api" / "user_configs"
    config_file = config_dir / f"frontend_config_{user_id}.json"
    return config_file


async def load_frontend_config_from_file(
    user_id: str, logger: Logger
) -> FrontendConfig:
    # save frontend config locally
    try:
        elysia_package_dir = Path(__file__).parent.parent.parent  # Gets to elysia/
        config_dir = elysia_package_dir / "elysia" / "api" / "user_configs"
        config_file = config_dir / f"frontend_config_{user_id}.json"
        print(f"\n\nLoading frontend config from file: {config_file}\n\n")

        if not config_file.exists():
            return FrontendConfig(logger=logger)

        with open(config_file, "r") as f:
            fe_config = await FrontendConfig.from_json(json.load(f), logger)
            return fe_config

    except Exception as e:
        logger.error(f"Error in save_frontend_config_to_file: {str(e)}")
        return FrontendConfig(logger=logger)


async def delete_config_after_completion(
    user_manager: UserManager, user_id: str, config_id: str
):
    client_manager = user_manager.users[user_id][
        "frontend_config"
    ].save_location_client_manager

    if client_manager.is_client:
        async with client_manager.connect_to_async_client() as client:
            if not await client.collections.exists("ELYSIA_CONFIG__"):
                return

            collection = client.collections.get("ELYSIA_CONFIG__")
            uuid = generate_uuid5(config_id)
            if await collection.data.exists(uuid):
                await collection.data.delete_by_id(uuid)

    if os.path.exists(f"elysia/api/user_configs/frontend_config_{user_id}.json"):
        os.remove(f"elysia/api/user_configs/frontend_config_{user_id}.json")


async def initialise_user_and_tree(user_id: str, conversation_id: str):
    user_manager = get_user_manager()

    response = await initialise_user(
        user_id,
        user_manager,
    )
    response = read_response(response)
    assert response["error"] == ""

    response = await initialise_tree(
        user_id,
        conversation_id,
        InitialiseTreeData(
            low_memory=False,
        ),
        user_manager,
    )
    response = read_response(response)
    assert response["error"] == ""


class TestConfig:
    user_manager = get_user_manager()

    @pytest.mark.asyncio
    async def test_set_save_location(self):
        user_id = "test_user_set_save_location"
        conversation_id = "test_conversation_set_save_location"
        config_id = "test_config_set_save_location"
        config_name = "Test set save location"
        try:
            await initialise_user_and_tree(user_id, conversation_id)

            # the user should have a save location from the .env
            user = await self.user_manager.get_user_local(user_id)
            assert user["frontend_config"].save_location_wcd_url == os.getenv("WCD_URL")
            assert user["frontend_config"].save_location_wcd_api_key == os.getenv(
                "WCD_API_KEY"
            )

            # update the save location to an invalid one
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={},
                    frontend_config={
                        "save_location_wcd_url": "test_incorrect_wcd_url",
                        "save_location_wcd_api_key": "test_incorrect_wcd_api_key",
                    },
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)

            # but the user should have a new save location
            user = await self.user_manager.get_user_local(user_id)
            assert (
                user["frontend_config"].save_location_wcd_url
                == "test_incorrect_wcd_url"
            )
            assert (
                user["frontend_config"].save_location_wcd_api_key
                == "test_incorrect_wcd_api_key"
            )
            warning_found = False
            for warning in response["warnings"]:
                warning_found = "Could not connect to Weaviate" in warning
            assert warning_found

            # same if no api keys are provided
            # update the save location to an invalid one
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={},
                    frontend_config={
                        "save_location_wcd_url": "",
                        "save_location_wcd_api_key": "",
                    },
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)

            warning_found = False
            for warning in response["warnings"]:
                warning_found = (
                    "No valid destination for config save location found" in warning
                )
            assert warning_found

        finally:
            await self.user_manager.close_all_clients()
            await delete_config_after_completion(self.user_manager, user_id, config_id)

    @pytest.mark.asyncio
    async def test_smart_setup_models_user(self):
        user_id = "test_user_smart_setup_models_user"
        conversation_id = "test_conversation_smart_setup_models_user"

        try:
            await initialise_user_and_tree(user_id, conversation_id)

            # check that the tree manager has the correct settings
            tree_manager = self.user_manager.users[user_id]["tree_manager"]

            assert tree_manager.settings.BASE_MODEL is not None
            assert tree_manager.settings.COMPLEX_MODEL is not None
            assert tree_manager.settings.BASE_PROVIDER is not None
            assert tree_manager.settings.COMPLEX_PROVIDER is not None

            # should default use environment variables
            assert tree_manager.settings.WCD_URL == os.getenv("WCD_URL")
            assert tree_manager.settings.WCD_API_KEY == os.getenv("WCD_API_KEY")
            assert tree_manager.config.style != ""
            assert tree_manager.config.agent_description != ""
            assert tree_manager.config.end_goal != ""
            assert tree_manager.config.branch_initialisation != ""

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_smart_setup_tree(self):
        user_id = "test_user_smart_setup_tree"
        conversation_id = "test_conversation_smart_setup_tree"
        try:
            await initialise_user_and_tree(user_id, conversation_id)
            tree: Tree = await self.user_manager.get_tree(user_id, conversation_id)

            # and the tree should have the correct models
            assert tree.settings.BASE_MODEL is not None
            assert tree.settings.COMPLEX_MODEL is not None
            assert tree.settings.BASE_PROVIDER is not None
            assert tree.settings.COMPLEX_PROVIDER is not None
        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_save_config_no_api_keys(self):
        user_id = "test_user_save_config_no_api_keys"
        conversation_id = "test_conversation_save_config_no_api_keys"
        config_id = f"test_config_conversation_save_config_no_api_keys"
        config_name = "Test save config no api keys"

        try:
            await initialise_user_and_tree(user_id, conversation_id)

            # Get tree manager in advance
            user = await self.user_manager.get_user_local(user_id)
            tree_manager = user["tree_manager"]

            # Save a config with no api keys
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={
                        "settings": {
                            "BASE_MODEL": "gpt-4o-mini",
                            "COMPLEX_MODEL": "gpt-4o",
                            "BASE_PROVIDER": "openai",
                            "COMPLEX_PROVIDER": "openai",
                            "WCD_URL": os.getenv("WCD_URL"),
                            "WCD_API_KEY": os.getenv("WCD_API_KEY"),
                            "API_KEYS": {},
                        },
                        "style": "Professional and concise.",
                        "agent_description": "You are a helpful assistant that searches data.",
                        "end_goal": "Provide a summary of the data.",
                        "branch_initialisation": "one_branch",
                    },
                    frontend_config={
                        "save_location_wcd_url": os.getenv("WCD_URL"),
                        "save_location_wcd_api_key": os.getenv("WCD_API_KEY"),
                    },
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

        finally:
            await self.user_manager.close_all_clients()
            await delete_config_after_completion(self.user_manager, user_id, config_id)

    @pytest.mark.asyncio
    async def test_change_config_user(self):
        user_id = "test_user_change_config_user"
        conversation_id = "test_conversation_change_config_user"
        config_id = f"test_config_conversation_change_config_user"
        config_name = "Test change config user"

        try:
            await initialise_user_and_tree(user_id, conversation_id)

            # Get tree manager in advance
            user = await self.user_manager.get_user_local(user_id)
            tree_manager = user["tree_manager"]

            # Set frontend config to not save configs to weaviate
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=False,
                    config={},
                    frontend_config={"save_configs_to_weaviate": False},
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == "", response["error"]
            assert response["warnings"] == [], "\n".join(response["warnings"])

            # Change user config
            new_settings = {
                "BASE_MODEL": "gpt-4o-mini",
                "COMPLEX_MODEL": "gpt-4o",
                "BASE_PROVIDER": "openai",
                "COMPLEX_PROVIDER": "openai",
            }
            new_style = "Professional and concise."
            new_agent_description = "You are a helpful assistant that searches data."
            new_branch_init = "one_branch"
            old_end_goal = tree_manager.config.end_goal

            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={
                        "settings": new_settings,
                        "style": new_style,
                        "agent_description": new_agent_description,
                        "branch_initialisation": new_branch_init,
                    },
                    frontend_config={},
                ),
                user_manager=self.user_manager,
            )

            # Verify response is OK
            response = read_response(response)
            assert response["error"] == "", response["error"]
            assert response["warnings"] == [], "\n".join(response["warnings"])

            assert tree_manager.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree_manager.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree_manager.settings.BASE_PROVIDER == "openai"
            assert tree_manager.settings.COMPLEX_PROVIDER == "openai"

            assert tree_manager.config.id == config_id
            assert tree_manager.config.style == new_style
            assert tree_manager.config.agent_description == new_agent_description
            assert (
                tree_manager.config.end_goal == old_end_goal
            )  # this parameter wasn't set so it should be the same as before
            assert tree_manager.config.branch_initialisation == new_branch_init

            # Verify model settings propagated to existing tree
            tree: Tree = await self.user_manager.get_tree(user_id, conversation_id)
            assert tree.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree.settings.BASE_PROVIDER == "openai"
            assert tree.settings.COMPLEX_PROVIDER == "openai"

            # And style, agent_description, etc. should have propagated to existing tree
            assert tree.tree_data.atlas.style == new_style
            assert tree.tree_data.atlas.agent_description == new_agent_description
            assert tree.branch_initialisation == new_branch_init

        finally:
            await self.user_manager.close_all_clients()
            await delete_config_after_completion(self.user_manager, user_id, config_id)

    @pytest.mark.asyncio
    async def test_change_config_tree(self):
        user_id = "test_user_change_config_tree"
        conversation_id = "test_conversation_change_config_tree"
        try:
            await initialise_user_and_tree(user_id, conversation_id)

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
                user_id=user_id,
                conversation_id=conversation_id,
                data=SaveConfigTreeData(
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
            # assert tree.branch_initialisation == new_branch_init

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
            assert tree_manager.config.style == initial_style

        finally:
            await self.user_manager.close_all_clients()

    @pytest.mark.asyncio
    async def test_config_workflow(self):
        user_id = "test_user_config_workflow"
        conversation_id_1 = "test_conversation_workflow_1"
        conversation_id_2 = "test_conversation_workflow_2"
        config_id = f"test_config_conversation_config_workflow"
        config_name = "Test config workflow"

        try:
            await initialise_user_and_tree(user_id, conversation_id_1)

            # Test changing config
            user_settings = {
                "BASE_MODEL": "gpt-4o-mini",
                "COMPLEX_MODEL": "gpt-4o",
                "BASE_PROVIDER": "openai",
                "COMPLEX_PROVIDER": "openai",
            }
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=False,
                    config={
                        "settings": user_settings,
                        "style": "Professional style for user",
                    },
                    frontend_config={
                        "save_configs_to_weaviate": False,
                    },
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Check tree manager settings have NOT changed because default=False
            tree_manager = self.user_manager.users[user_id]["tree_manager"]
            assert tree_manager.settings.BASE_MODEL != "gpt-4o-mini"
            assert tree_manager.settings.COMPLEX_MODEL != "gpt-4o"
            assert tree_manager.settings.BASE_PROVIDER != "openai"
            assert tree_manager.settings.COMPLEX_PROVIDER != "openai"

            # save again with default=True
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={
                        "settings": user_settings,
                        "style": "Professional style for user",
                    },
                    frontend_config={
                        "save_configs_to_weaviate": False,
                    },
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            assert tree_manager.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree_manager.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree_manager.settings.BASE_PROVIDER == "openai"
            assert tree_manager.settings.COMPLEX_PROVIDER == "openai"

            # Verify tree 1 inherits user model settings including style
            tree1: Tree = await self.user_manager.get_tree(user_id, conversation_id_1)
            assert tree1.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree1.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree1.tree_data.atlas.style == "Professional style for user"

            # Create tree 2
            response = await initialise_tree(
                user_id,
                conversation_id_2,
                data=InitialiseTreeData(
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
                user_id=user_id,
                conversation_id=conversation_id_1,
                data=SaveConfigTreeData(
                    settings=tree1_settings,
                    style="Custom tree 1 style",
                    agent_description="Custom tree 1 agent description",
                    end_goal="Custom tree 1 end goal",
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
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={
                        "settings": new_user_settings,
                    },
                    frontend_config={},
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

        finally:
            await self.user_manager.close_all_clients()
            await delete_config_after_completion(self.user_manager, user_id, config_id)

    @pytest.mark.asyncio
    async def test_save_config(self):
        user_id = "test_user_save_config"
        conversation_id = "test_conversation_save_config"
        config_id = f"test_config_conversation_save_config"
        config_name = "Test config save"

        try:
            await initialise_user_and_tree(user_id, conversation_id)

            # create a config and save
            user = await self.user_manager.get_user_local(user_id)
            tree_manager: TreeManager = user["tree_manager"]

            new_settings = {
                "WCD_URL": os.getenv("TESTING_WCD_URL"),
                "WCD_API_KEY": os.getenv("TESTING_WCD_API_KEY"),
            }

            # check that the first WCD_URL etc is the env one and not the new_settings ones
            config = user["tree_manager"].config.to_json()
            assert config["settings"]["WCD_URL"] == os.getenv("WCD_URL")
            assert config["settings"]["WCD_API_KEY"] == os.getenv("WCD_API_KEY")

            assert config["settings"]["WCD_URL"] != new_settings["WCD_URL"]
            assert config["settings"]["WCD_API_KEY"] != new_settings["WCD_API_KEY"]

            # change config
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=False,
                    config={
                        "settings": new_settings,
                        "style": "Test style",
                        "agent_description": "Test description",
                        "end_goal": "Test end goal",
                        "branch_initialisation": tree_manager.config.branch_initialisation,
                    },
                    frontend_config={},
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # check the things were updated
            # assert response["config"][""

            # verify the config was saved by listing all configs
            response = await list_configs(
                user_id=user_id,
                user_manager=self.user_manager,
            )

            response = read_response(response)
            assert response["error"] == ""
            assert config_id in [c["config_id"] for c in response["configs"]]

        finally:
            await self.user_manager.close_all_clients()
            await delete_config_after_completion(self.user_manager, user_id, config_id)

    @pytest.mark.asyncio
    async def test_load_config_user(self):
        user_id = "test_user_load_config_user"
        conversation_id = "test_conversation_load_config_user"
        config_id = f"test_config_user"
        config_name = "Test config user"

        try:
            await initialise_user_and_tree(user_id, conversation_id)

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
            custom_branch_init = "multi_branch"

            # change user settings to these values
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={
                        "settings": settings,
                        "style": custom_style,
                        "agent_description": custom_agent_description,
                        "end_goal": custom_end_goal,
                        "branch_initialisation": custom_branch_init,
                    },
                    frontend_config={},
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # now change settings to something else WITHOUT saving
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=False,
                    config={
                        "settings": {
                            "BASE_MODEL": "claude-3-haiku",
                            "COMPLEX_MODEL": "claude-3-opus",
                            "BASE_PROVIDER": "anthropic",
                            "COMPLEX_PROVIDER": "anthropic",
                        },
                        "style": "Conversational and friendly.",
                        "agent_description": "You are a friendly assistant.",
                        "end_goal": "Provide helpful and friendly responses.",
                        "branch_initialisation": "one_branch",
                    },
                    frontend_config={
                        "save_configs_to_weaviate": False,
                    },
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Load the config back for the user
            response = await load_config_user(
                user_id=user_id,
                config_id=config_id,
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
            assert tree_manager.config.style == custom_style
            assert tree_manager.config.agent_description == custom_agent_description
            assert tree_manager.config.end_goal == custom_end_goal
            # assert tree_manager.config.branch_initialisation == custom_branch_init

        finally:
            await self.user_manager.close_all_clients()
            await delete_config_after_completion(self.user_manager, user_id, config_id)

    @pytest.mark.asyncio
    async def test_load_config_tree(self):
        """Test loading a config for a tree from the Weaviate database."""
        user_id = "test_user_load_config_tree"
        config_id = "test_config_tree"
        conversation_id = "test_conversation_load_config_tree"
        config_name = "Test config tree"
        try:
            await initialise_user_and_tree(user_id, conversation_id)

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

            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={
                        "settings": settings,
                        "style": custom_style,
                        "agent_description": custom_agent_description,
                        "end_goal": custom_end_goal,
                        "branch_initialisation": custom_branch_init,
                    },
                    frontend_config={},
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Load the config for the tree (just settings, not atlas or branch init)
            response = await load_config_tree(
                user_id=user_id,
                conversation_id=conversation_id,
                config_id=config_id,
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

            # Load everything now
            response = await load_config_tree(
                user_id=user_id,
                conversation_id=conversation_id,
                config_id=config_id,
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
            # assert tree.branch_initialisation == custom_branch_init

            # User level settings should remain unchanged
            user = await self.user_manager.get_user_local(user_id)
            tree_manager = user["tree_manager"]
            assert tree_manager.settings.BASE_MODEL == "gpt-4-turbo"
            assert tree_manager.settings.COMPLEX_MODEL == "gpt-4-vision"
            assert tree_manager.config.style == custom_style

        finally:
            await self.user_manager.close_all_clients()
            await delete_config_after_completion(self.user_manager, user_id, config_id)

    @pytest.mark.asyncio
    async def test_list_configs(self):
        """Test listing configs from the Weaviate database."""
        user_id = "test_user_list_configs"
        conversation_id = "test_conversation_list_configs"
        config_ids = [
            f"test_config_list_{i}_{random.randint(0, 1000000)}" for i in range(3)
        ]
        try:
            await initialise_user_and_tree(user_id, conversation_id)

            # Save multiple configs
            for i, config_id in enumerate(config_ids):
                config = SaveConfigUserData(
                    name=f"Test config list {i}",
                    default=False,
                    config={
                        "settings": {
                            "BASE_MODEL": f"model-{i}",
                            "COMPLEX_MODEL": f"complex-model-{i}",
                            "BASE_PROVIDER": "test-provider",
                            "COMPLEX_PROVIDER": "test-provider",
                        },
                        "style": f"Style {i}",
                        "agent_description": f"Agent description {i}",
                        "end_goal": f"End goal {i}",
                        "branch_initialisation": "one_branch",
                    },
                    frontend_config={},
                )

                response = await save_config_user(
                    user_id=user_id,
                    config_id=config_id,
                    data=config,
                    user_manager=get_user_manager(),
                )
                response = read_response(response)
                assert response["error"] == ""

            response = await list_configs(
                user_id=user_id,
                user_manager=get_user_manager(),
            )
            response = read_response(response)
            assert response["error"] == ""

            for config_id in config_ids:
                assert config_id in [c["config_id"] for c in response["configs"]]

        finally:
            await self.user_manager.close_all_clients()
            for config_id in config_ids:
                await delete_config_after_completion(
                    self.user_manager, user_id, config_id
                )

    @pytest.mark.asyncio
    async def test_config_save_load_workflow(self):
        """Test a workflow of saving and loading configs between users and trees."""
        user_id_1 = "test_user_config_workflow_1"
        conversation_id_1 = "test_conversation_workflow_1"
        conversation_id_2 = "test_conversation_workflow_2"
        config_id = "test_shared_config_workflow"
        config_name = "Test shared config workflow"

        try:
            await initialise_user_and_tree(user_id_1, conversation_id_1)

            # Initialize the user with custom settings
            custom_settings = {
                "BASE_MODEL": "gpt-4o-mini",
                "COMPLEX_MODEL": "gpt-4o",
                "BASE_PROVIDER": "openai",
                "COMPLEX_PROVIDER": "openai",
            }
            custom_style = "Original style"
            custom_agent_description = "Original agent description"
            custom_end_goal = "Original end goal"

            # Apply the config
            user1 = await self.user_manager.get_user_local(user_id_1)
            tree_manager1: TreeManager = user1["tree_manager"]

            response = await save_config_user(
                user_id=user_id_1,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={
                        "settings": tree_manager1.settings.to_json(),
                        "style": custom_style,
                        "agent_description": custom_agent_description,
                        "end_goal": custom_end_goal,
                        "branch_initialisation": tree_manager1.config.branch_initialisation,
                    },
                    frontend_config={
                        "save_configs_to_weaviate": False,
                    },
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # update frontend config so that configs are saved to weaviate
            response = await save_config_user(
                user_id=user_id_1,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={
                        "settings": custom_settings,
                        "style": custom_style,
                        "agent_description": custom_agent_description,
                        "end_goal": custom_end_goal,
                        "branch_initialisation": tree_manager1.config.branch_initialisation,
                    },
                    frontend_config={
                        "save_location_wcd_url": os.getenv("WCD_URL"),
                        "save_location_wcd_api_key": os.getenv("WCD_API_KEY"),
                        "save_trees_to_weaviate": False,
                        "save_configs_to_weaviate": True,
                    },
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # list configs
            response = await list_configs(
                user_id=user_id_1,
                user_manager=self.user_manager,
            )
            list_response1 = read_response(response)
            assert config_id in [c["config_id"] for c in list_response1["configs"]]

            # change the config only in-memory
            response = await save_config_user(
                user_id=user_id_1,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={
                        "settings": {
                            "BASE_MODEL": "claude-3-haiku",
                            "BASE_PROVIDER": "anthropic",
                        },
                        "style": "New incorrect style",
                        "agent_description": "New incorrect agent description",
                        "end_goal": "New incorrect end goal",
                        "branch_initialisation": tree_manager1.config.branch_initialisation,
                    },
                    frontend_config={
                        "save_configs_to_weaviate": False,
                    },
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # check the new config options are applied
            user1 = await self.user_manager.get_user_local(user_id_1)
            tree_manager1: TreeManager = user1["tree_manager"]
            assert tree_manager1.settings.BASE_MODEL == "claude-3-haiku"
            assert tree_manager1.settings.BASE_PROVIDER == "anthropic"
            assert tree_manager1.config.style == "New incorrect style"
            assert (
                tree_manager1.config.agent_description
                == "New incorrect agent description"
            )
            assert tree_manager1.config.end_goal == "New incorrect end goal"

            # Now load the config to the user
            response = await load_config_user(
                user_id=user_id_1,
                config_id=config_id,
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Now verify the new settings were loaded
            user1 = await self.user_manager.get_user_local(user_id_1)
            tree_manager1: TreeManager = user1["tree_manager"]
            assert tree_manager1.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree_manager1.config.style == "Original style"
            assert (
                tree_manager1.config.agent_description == "Original agent description"
            )
            assert tree_manager1.config.end_goal == "Original end goal"

            user1_frontend_config = user1["frontend_config"]
            assert user1_frontend_config.save_location_wcd_url == os.getenv("WCD_URL")
            assert user1_frontend_config.save_location_wcd_api_key == os.getenv(
                "WCD_API_KEY"
            )
            assert user1_frontend_config.config["save_trees_to_weaviate"] == False

            # Make a new tree for this user
            response = await initialise_tree(
                user_id=user_id_1,
                conversation_id=conversation_id_2,
                data=InitialiseTreeData(
                    low_memory=True,
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # dont save
            response = await update_frontend_config(
                user_id=user_id_1,
                data=UpdateFrontendConfigData(
                    config={"save_configs_to_weaviate": False},
                ),
                user_manager=self.user_manager,
            )

            # change the config globally for the user
            response = await save_config_user(
                user_id=user_id_1,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={
                        "settings": {
                            "BASE_MODEL": "claude-3-5-sonnet",
                            "BASE_PROVIDER": "anthropic",
                        },
                        "style": "New updated style",
                        "agent_description": "New updated agent description",
                        "end_goal": "New updated end goal",
                        "branch_initialisation": tree_manager1.config.branch_initialisation,
                    },
                    frontend_config={},
                ),
                user_manager=self.user_manager,
            )

            # Changes to user should propagate to the tree (not used its own settings)
            tree2: Tree = await self.user_manager.get_tree(user_id_1, conversation_id_2)
            assert tree2.settings.BASE_MODEL == "claude-3-5-sonnet"  # this one changes
            assert tree2.tree_data.atlas.style == "New updated style"
            assert (
                tree2.tree_data.atlas.agent_description
                == "New updated agent description"
            )
            assert tree2.tree_data.atlas.end_goal == "New updated end goal"

            # Load the config to the new tree 1 directly
            response = await load_config_tree(
                user_id=user_id_1,
                conversation_id=conversation_id_2,
                config_id=config_id,
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # Verify tree has the ORIGINAL settings (from the save/load)
            tree2 = await self.user_manager.get_tree(user_id_1, conversation_id_2)
            assert tree2.settings.BASE_MODEL == "gpt-4o-mini"
            assert tree2.settings.COMPLEX_MODEL == "gpt-4o"
            assert tree2.tree_data.atlas.style == "Original style"
            assert (
                tree2.tree_data.atlas.agent_description == "Original agent description"
            )
            assert tree2.tree_data.atlas.end_goal == "Original end goal"

        finally:
            await self.user_manager.close_all_clients()
            await delete_config_after_completion(
                self.user_manager, user_id_1, config_id
            )

    @pytest.mark.asyncio
    async def test_delete_config(self):
        """Test deleting a config from the Weaviate database."""
        user_id = "test_user_delete_config"
        conversation_id = "test_conversation_delete_config"
        config_id = "test_delete_config"
        config_name = "Test delete config"
        try:
            await initialise_user_and_tree(user_id, conversation_id)

            # create a config and save
            user = await self.user_manager.get_user_local(user_id)
            tree_manager: TreeManager = user["tree_manager"]

            # change config
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=False,
                    config={
                        "settings": tree_manager.settings.to_json(),
                        "style": tree_manager.config.style,
                        "agent_description": tree_manager.config.agent_description,
                        "end_goal": tree_manager.config.end_goal,
                        "branch_initialisation": tree_manager.config.branch_initialisation,
                    },
                    frontend_config={},
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # verify the config was saved by listing all configs
            response = await list_configs(
                user_id=user_id,
                user_manager=self.user_manager,
            )

            response = read_response(response)
            assert response["error"] == ""
            assert config_id in [c["config_id"] for c in response["configs"]]

            # delete the config
            response = await delete_config(
                user_id=user_id,
                config_id=config_id,
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # verify the config was deleted by listing all configs
            response = await list_configs(
                user_id=user_id,
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""
            assert config_id not in [c["config_id"] for c in response["configs"]]

        finally:
            await self.user_manager.close_all_clients()
            await delete_config_after_completion(self.user_manager, user_id, config_id)

    @pytest.mark.asyncio
    async def test_frontend_config_local(self):
        user_id = "test_user_frontend_config_local"
        conversation_id = "test_conversation_frontend_config_local"
        config_id = f"test_frontend_config_local"
        config_name = "Test frontend config local"

        try:
            await initialise_user_and_tree(user_id, conversation_id)

            # create a config and save
            user = await self.user_manager.get_user_local(user_id)
            tree_manager: TreeManager = user["tree_manager"]

            # change config
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    default=True,
                    config={},
                    frontend_config={
                        "save_trees_to_weaviate": False,
                        "save_configs_to_weaviate": False,
                    },
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)

            # check existence of local file
            assert os.path.exists(get_frontend_config_file_path(user_id))

            # check the local file has the correct values
            fe_config = await load_frontend_config_from_file(user_id, logger)
            fe_config = fe_config.to_json()

            assert fe_config["save_location_wcd_url"] == os.getenv("WCD_URL")
            assert fe_config["save_location_wcd_api_key"] == os.getenv("WCD_API_KEY")
            assert fe_config["save_trees_to_weaviate"] == False
            assert fe_config["save_configs_to_weaviate"] == False

            # remove user from user manager
            del self.user_manager.users[user_id]

            # add user back to user manager
            await self.user_manager.add_user_local(user_id)

            # check the frontend config is loaded from the local file
            user = await self.user_manager.get_user_local(user_id)
            assert user["frontend_config"].save_location_wcd_url == os.getenv("WCD_URL")
            assert user["frontend_config"].save_location_wcd_api_key == os.getenv(
                "WCD_API_KEY"
            )
            assert user["frontend_config"].config["save_trees_to_weaviate"] == False
            assert user["frontend_config"].config["save_configs_to_weaviate"] == False

        finally:
            await self.user_manager.close_all_clients()
            await delete_config_after_completion(self.user_manager, user_id, config_id)

    # @pytest.mark.asyncio
    # async def test_default_config_for_user(self):
    #     user_id = "test_user_default_config_for_user"
    #     conversation_id = "test_conversation_default_config_for_user"
    #     config_id = f"test_default_config_for_user"
    #     config_id_2 = f"test_default_config_for_user_2"
    #     config_name = "Test default config for user"

    #     try:
    #         # create new user
    #         await initialise_user_and_tree(user_id, conversation_id)

    #         # save a config
    #         response = await save_config_user(
    #             user_id=user_id,
    #             config_id=config_id,
    #             data=SaveConfigUserData(
    #                 name=config_name,
    #                 default=True,
    #                 config={
    #                     "settings": {
    #                         "BASE_MODEL": "gpt-4o-mini",
    #                         "BASE_PROVIDER": "openai",
    #                         "WCD_URL": os.getenv("WCD_URL"),
    #                         "WCD_API_KEY": os.getenv("WCD_API_KEY"),
    #                         "API_KEYS": {
    #                             "openai_api_key": os.getenv("OPENAI_API_KEY"),
    #                         },
    #                     },
    #                     "style": "New style for default",
    #                     "agent_description": "New agent description for default",
    #                     "end_goal": "New end goal for default",
    #                     "branch_initialisation": "one_branch",
    #                 },
    #                 frontend_config={
    #                     "save_trees_to_weaviate": False,
    #                     "save_configs_to_weaviate": True,
    #                 },
    #             ),
    #             user_manager=self.user_manager,
    #         )
    #         response = read_response(response)
    #         assert response["error"] == ""

    #         # check the config was saved
    #         response = await list_configs(
    #             user_id=user_id,
    #             user_manager=self.user_manager,
    #         )
    #         response = read_response(response)
    #         assert config_id in [c["config_id"] for c in response["configs"]]

    #         # remove the user from the user manager
    #         del self.user_manager.users[user_id]

    #         # add the user back to the user manager
    #         response = await initialise_user(
    #             user_id,
    #             user_manager=self.user_manager,
    #         )
    #         response = read_response(response)
    #         assert response["error"] == ""

    #         assert response["config"]["id"] == config_id
    #         assert response["config"]["settings"]["BASE_MODEL"] == "gpt-4o-mini"
    #         assert response["config"]["settings"]["BASE_PROVIDER"] == "openai"
    #         assert response["config"]["style"] == "New style for default"
    #         assert (
    #             response["config"]["agent_description"]
    #             == "New agent description for default"
    #         )
    #         assert response["config"]["end_goal"] == "New end goal for default"
    #         assert response["config"]["branch_initialisation"] == "one_branch"

    #         assert response["frontend_config"]["save_trees_to_weaviate"] == False
    #         assert response["frontend_config"]["save_configs_to_weaviate"] == True

    #         # save a new config which is not default
    #         response = await save_config_user(
    #             user_id=user_id,
    #             config_id=config_id_2,
    #             data=SaveConfigUserData(
    #                 name=config_name,
    #                 default=False,
    #                 config={
    #                     "settings": {
    #                         "BASE_MODEL": "gpt-4.1-mini",
    #                         "BASE_PROVIDER": "openai",
    #                         "WCD_URL": os.getenv("WCD_URL"),
    #                         "WCD_API_KEY": os.getenv("WCD_API_KEY"),
    #                         "API_KEYS": {
    #                             "openai_api_key": os.getenv("OPENAI_API_KEY"),
    #                         },
    #                     },
    #                     "style": "New style for non-default",
    #                     "agent_description": "New agent description for non-default",
    #                     "end_goal": "New end goal for non-default",
    #                     "branch_initialisation": "one_branch",
    #                 },
    #                 frontend_config={
    #                     "save_location_wcd_url": os.getenv("WCD_URL"),
    #                     "save_location_wcd_api_key": os.getenv("WCD_API_KEY"),
    #                     "save_trees_to_weaviate": False,
    #                     "save_configs_to_weaviate": True,
    #                 },
    #             ),
    #             user_manager=self.user_manager,
    #         )
    #         response = read_response(response)
    #         assert response["error"] == ""

    #         # delete and create the user
    #         del self.user_manager.users[user_id]
    #         response = await initialise_user(
    #             user_id,
    #             user_manager=self.user_manager,
    #         )
    #         response = read_response(response)
    #         assert response["error"] == ""

    #         # should still have the old config, not the new one
    #         assert response["config"]["id"] == config_id
    #         assert response["config"]["settings"]["BASE_MODEL"] == "gpt-4o-mini"
    #         assert response["config"]["settings"]["BASE_PROVIDER"] == "openai"
    #         assert response["config"]["style"] == "New style for default"
    #         assert (
    #             response["config"]["agent_description"]
    #             == "New agent description for default"
    #         )
    #         assert response["config"]["end_goal"] == "New end goal for default"
    #         assert response["config"]["branch_initialisation"] == "one_branch"

    #         assert response["frontend_config"]["save_trees_to_weaviate"] == False
    #         assert response["frontend_config"]["save_configs_to_weaviate"] == True

    #         # but we can still see the old one in the list
    #         response = await list_configs(
    #             user_id=user_id,
    #             user_manager=self.user_manager,
    #         )
    #         response = read_response(response)
    #         assert config_id_2 in [c["config_id"] for c in response["configs"]]

    #         # and load it
    #         response = await load_config_user(
    #             user_id=user_id,
    #             config_id=config_id_2,
    #             user_manager=self.user_manager,
    #         )
    #         response = read_response(response)
    #         assert response["error"] == ""

    #         # check the config was loaded
    #         user = await self.user_manager.get_user_local(user_id)
    #         assert user["tree_manager"].config.style == "New style for non-default"
    #         assert (
    #             user["tree_manager"].config.agent_description
    #             == "New agent description for non-default"
    #         )
    #         assert (
    #             user["tree_manager"].config.end_goal == "New end goal for non-default"
    #         )

    #     finally:
    #         await self.user_manager.close_all_clients()
    #         await delete_config_after_completion(self.user_manager, user_id, config_id)

    @pytest.mark.asyncio
    async def test_new_config(self):
        user_id = "test_user_new_config"
        conversation_id = "test_conversation_new_config"
        config_id = f"test_new_config"
        config_name = "Test new config"

        try:
            await initialise_user_and_tree(user_id, conversation_id)

            # create a new config
            response = await new_user_config(
                user_id=user_id,
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""
            new_user_config_id = response["config"]["id"]

            # save config
            response = await save_config_user(
                user_id=user_id,
                config_id=new_user_config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    id=new_user_config_id,
                    default=True,
                    config=response["config"],
                    frontend_config={},
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            response = await initialise_user(
                user_id,
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""
            assert response["config"]["id"] == new_user_config_id

        finally:
            await self.user_manager.close_all_clients()
            try:
                await delete_config_after_completion(
                    self.user_manager, user_id, new_user_config_id
                )
            except Exception as e:
                pass

    @pytest.mark.asyncio
    async def test_new_config_no_overwrite(self):
        user_id = "test_user_new_config_no_overwrite"
        conversation_id = "test_conversation_new_config_no_overwrite"
        config_name = "Test new config no overwrite"

        try:
            await initialise_user_and_tree(user_id, conversation_id)

            # get config id
            user = await self.user_manager.get_user_local(user_id)
            config_id = user["tree_manager"].config.id

            # save some values
            response = await save_config_user(
                user_id=user_id,
                config_id=config_id,
                data=SaveConfigUserData(
                    name=config_name,
                    id=config_id,
                    default=True,
                    config={
                        "settings": {
                            "BASE_MODEL": "gpt-4o-mini",
                            "BASE_PROVIDER": "openai",
                            "COMPLEX_MODEL": "gpt-4o",
                            "COMPLEX_PROVIDER": "openai",
                            "WCD_URL": os.getenv("WCD_URL"),
                            "WCD_API_KEY": os.getenv("WCD_API_KEY"),
                            "API_KEYS": {
                                "openai_api_key": os.getenv("OPENAI_API_KEY"),
                            },
                        },
                        "style": "New style for no overwrite",
                        "agent_description": "New agent description for no overwrite",
                        "end_goal": "New end goal for no overwrite",
                        "branch_initialisation": "one_branch",
                    },
                    frontend_config={
                        "save_location_wcd_url": os.getenv("WCD_URL"),
                        "save_location_wcd_api_key": os.getenv("WCD_API_KEY"),
                        "save_trees_to_weaviate": True,
                        "save_configs_to_weaviate": True,
                    },
                ),
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""

            # create a new config
            response = await new_user_config(
                user_id=user_id,
                user_manager=self.user_manager,
            )
            response = read_response(response)
            assert response["error"] == ""
            new_config_id = response["config"]["id"]

            # check the user values were NOT saved
            user = await self.user_manager.get_user_local(user_id)
            assert user["tree_manager"].config.id == config_id
            assert user["tree_manager"].config.settings.BASE_MODEL == "gpt-4o-mini"
            assert user["tree_manager"].config.settings.BASE_PROVIDER == "openai"
            assert user["tree_manager"].config.settings.COMPLEX_MODEL == "gpt-4o"
            assert user["tree_manager"].config.settings.COMPLEX_PROVIDER == "openai"

        finally:
            await self.user_manager.close_all_clients()
            try:
                await delete_config_after_completion(
                    self.user_manager, user_id, new_config_id
                )

            except Exception as e:
                pass

            try:
                await delete_config_after_completion(
                    self.user_manager, user_id, config_id
                )
            except Exception as e:
                pass

    @pytest.mark.asyncio
    async def test_get_models(self):
        response = await get_models()
        response = read_response(response)
        assert response["error"] == ""
        assert "models" in response
        assert len(response["models"]) > 0
        assert "openai" in response["models"]
        assert "anthropic" in response["models"]
        assert "gemini" in response["models"]
