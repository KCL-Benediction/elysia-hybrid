# TODO: with user management: per-user config that gets saved to the user's db i.e. ELYSIA_CONFIG__ as a collection
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from dotenv import load_dotenv, set_key

load_dotenv(override=True)

# API Types
from elysia.api.api_types import (
    ChangeConfigUserData,
    ChangeConfigTreeData,
    DefaultModelsUserData,
    DefaultModelsTreeData,
    EnvironmentSettingsUserData,
    LoadConfigUserData,
    SaveConfigData,
    LoadConfigTreeData,
    ListConfigsData,
    InitialiseUserData,
    Config,
)

from elysia.api.core.log import logger
from elysia.api.dependencies.common import get_user_manager
from elysia.api.services.user import UserManager
from elysia.util.client import ClientManager
from elysia.util.parsing import format_dict_to_serialisable
from elysia.config import Settings
from elysia.api.services.tree import TreeManager
from elysia.tree.tree import Tree
from weaviate.util import generate_uuid5
import weaviate.classes.config as wc


def rename_keys(config_item: dict):

    renamed_settings = {
        key.upper(): config_item["settings"][key] for key in config_item["settings"]
    }

    if "API_KEYS" in config_item["settings"]:
        renamed_api_keys = {
            key.lower(): config_item["settings"]["API_KEYS"][key]
            for key in config_item["settings"]["API_KEYS"]
        }
        renamed_settings["API_KEYS"] = renamed_api_keys

    renamed_config = {key.lower(): config_item[key] for key in config_item}
    renamed_config["settings"] = renamed_settings

    return renamed_config


router = APIRouter()


@router.post("/default_models_user")
async def default_models_user(
    data: DefaultModelsUserData, user_manager: UserManager = Depends(get_user_manager)
):
    """
    Set the base_model and complex_model to the default values (gemini 2.0 flash or environment variables), for an entire user.
    Any changes will propagate to all trees associated with the user that were not initialised with their own settings.

    Args:
        data (DefaultModelsData): A class with the following attributes:
            user_id (str): The user ID.
        user_manager (UserManager): The user manager instance.

    Returns:
        JSONResponse: A JSON response with the following attributes:
            error (str): An error message. Empty if no error.
            config (dict): A dictionary of the updated config values.
    """
    logger.debug(f"/default_models_user API request received")
    logger.debug(f"User ID: {data.user_id}")

    try:
        user = await user_manager.get_user_local(data.user_id)
        tree_manager: TreeManager = user["tree_manager"]
        tree_manager.settings.default_models()

        config = Config(
            settings=tree_manager.settings.to_json(),
            style=tree_manager.style,
            agent_description=tree_manager.agent_description,
            end_goal=tree_manager.end_goal,
            branch_initialisation=tree_manager.branch_initialisation,
        )

    except Exception as e:
        logger.exception(f"Error in /default_models_user API")
        return JSONResponse(content={"error": str(e), "config": {}})

    return JSONResponse(content={"error": "", "config": config.model_dump()})


@router.post("/default_models_tree")
async def default_models_tree(
    data: DefaultModelsTreeData, user_manager: UserManager = Depends(get_user_manager)
):
    """
    Set the config in a single tree / conversation to the default values (gemini 2.0 flash or environment variables).
    Any changes will only affect this one tree / conversation.

    Args:
        data (DefaultModelsData): A class with the following attributes:
            user_id (str): The user ID.
            conversation_id (str): The conversation ID.
        user_manager (UserManager): The user manager instance.

    Returns:
        JSONResponse: A JSON response with the following attributes:
            error (str): An error message. Empty if no error.
            config (dict): A dictionary of the updated config values.
    """
    logger.debug(f"/default_models_tree API request received")
    logger.debug(f"User ID: {data.user_id}")
    logger.debug(f"Conversation ID: {data.conversation_id}")

    try:
        tree: Tree = await user_manager.get_tree(data.user_id, data.conversation_id)
        tree.default_models()

        config = Config(
            settings=tree.settings.to_json(),
            style=tree.tree_data.atlas.style,
            agent_description=tree.tree_data.atlas.agent_description,
            end_goal=tree.tree_data.atlas.end_goal,
            branch_initialisation=tree.branch_initialisation,
        )

    except Exception as e:
        logger.exception(f"Error in /default_models_tree API")
        return JSONResponse(content={"error": str(e), "config": {}})

    return JSONResponse(content={"error": "", "config": config.model_dump()})


@router.post("/environment_settings_user")
async def environment_settings_user(
    data: EnvironmentSettingsUserData,
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Set the settings for a user, to be used as default settings for all trees associated with that user.
    These will have been automatically set if none were provided during the initialisation of the user (initialise_user).
    Any changes to the api keys will be automatically propagated to the ClientManager for that user.

    Args:
        data (EnvironmentSettingsUserData): A class with the following attributes:
            user_id (str): The user ID.
        user_manager (UserManager): The user manager instance.

    Returns:
        JSONResponse: A JSON response with the following attributes:
            error (str): An error message. Empty if no error.
            config (dict): A dictionary of the updated config values.
    """

    try:
        user = await user_manager.get_user_local(data.user_id)
        tree_manager: TreeManager = user["tree_manager"]
        tree_manager.settings.set_api_keys_from_env()

        client_manager: ClientManager = user["client_manager"]
        await client_manager.set_keys_from_settings(tree_manager.settings)

        config = Config(
            settings=tree_manager.settings.to_json(),
            style=tree_manager.style,
            agent_description=tree_manager.agent_description,
            end_goal=tree_manager.end_goal,
            branch_initialisation=tree_manager.branch_initialisation,
        )

    except Exception as e:
        logger.exception(f"Error in /environment_settings_user API")
        return JSONResponse(content={"error": str(e), "config": {}})

    return JSONResponse(content={"error": "", "config": config.model_dump()})


@router.post("/change_user")
async def change_config_user(
    data: ChangeConfigUserData, user_manager: UserManager = Depends(get_user_manager)
):
    """
    Change the global config for a user.
    The `config` dictionary can contain any of the settings (dict), style, agent_description, end_goal and branch_initialisation.
    You do not need to specify all the settings, only the ones you wish to change.

    Any changes to the _settings_ will propagate to all trees associated with the user that were not initialised with their own settings,
    as well as update the ClientManager to use the new API keys.
    However, changes to the _style_, _agent_description_, _end_goal_ and _branch_initialisation_ will not be changed for existing trees.
    I.e., only changes to API keys and model choices will be changed for existing trees (Settings).

    Args:
        data (ChangeConfigUserData): A class with the following attributes:
            user_id (str): Required. The user ID.
            settings (dict): Optional. A dictionary of settings values to set, follows the same format as the Settings.configure() method.
            style (str): Optional. The writing style of the agent.
            agent_description (str): Optional. The description of the agent.
            end_goal (str): Optional. The end goal of the agent.
            branch_initialisation (str): Optional. The branch initialisation of the agent.
        user_manager (UserManager): The user manager instance.

    Returns:
        JSONResponse: A JSON response with the following attributes:
            error (str): An error message. Empty if no error.
            config (dict): A dictionary of the updated config values.
    """
    logger.debug(f"/change_config_user API request received")
    logger.debug(f"User ID: {data.user_id}")
    logger.debug(f"Settings: {data.settings}")
    logger.debug(f"Style: {data.style}")
    logger.debug(f"Agent description: {data.agent_description}")
    logger.debug(f"End goal: {data.end_goal}")
    logger.debug(f"Branch initialisation: {data.branch_initialisation}")

    try:
        user = await user_manager.get_user_local(data.user_id)
        tree_manager: TreeManager = user["tree_manager"]

        if data.settings is not None:
            tree_manager.settings.configure(**data.settings)

        if data.style is not None:
            tree_manager.change_style(data.style)

        if data.agent_description is not None:
            tree_manager.change_agent_description(data.agent_description)

        if data.end_goal is not None:
            tree_manager.change_end_goal(data.end_goal)

        if data.branch_initialisation is not None:
            tree_manager.change_branch_initialisation(data.branch_initialisation)

        client_manager: ClientManager = user["client_manager"]
        await client_manager.set_keys_from_settings(tree_manager.settings)

        config = Config(
            settings=tree_manager.settings.to_json(),
            style=tree_manager.style,
            agent_description=tree_manager.agent_description,
            end_goal=tree_manager.end_goal,
            branch_initialisation=tree_manager.branch_initialisation,
        )

    except Exception as e:
        logger.exception(f"Error in /change_config_user API")
        return JSONResponse(content={"error": str(e), "config": {}})

    return JSONResponse(content={"error": "", "config": config.model_dump()})


@router.post("/change_config_tree")
async def change_config_tree(
    data: ChangeConfigTreeData, user_manager: UserManager = Depends(get_user_manager)
):
    """
    Change the config for a single tree / conversation.
    The `config` dictionary can contain any of the settings (dict), style, agent_description, end_goal and branch_initialisation.
    You do not need to specify all the settings, only the ones you wish to change.

    Once you change the config, the tree will no longer inherit from the user's config.

    In this case, you cannot change the API keys, it will always inherit from the user's config.
    Any API keys provided will be ignored.

    Args:
        data (ChangeConfigData): A class with the following attributes:
            user_id (str): Required. The user ID.
            config (dict): Optional. A dictionary of config values to set, follows the same format as the Settings.configure() method.
            style (str): Optional. The writing style of the agent.
            agent_description (str): Optional. The description of the agent.
            end_goal (str): Optional. The end goal of the agent.
            branch_initialisation (str): Optional. The branch initialisation of the agent.
        user_manager (UserManager): The user manager instance.

    Returns:
        JSONResponse: A JSON response with the following attributes:
            error (str): An error message. Empty if no error.
            config (dict): A dictionary of the updated config values.
    """
    logger.debug(f"/change_config_tree API request received")
    logger.debug(f"User ID: {data.user_id}")
    logger.debug(f"Conversation ID: {data.conversation_id}")
    logger.debug(f"Settings: {data.settings}")
    logger.debug(f"Style: {data.style}")
    logger.debug(f"Agent description: {data.agent_description}")
    logger.debug(f"End goal: {data.end_goal}")
    logger.debug(f"Branch initialisation: {data.branch_initialisation}")

    try:
        tree: Tree = await user_manager.get_tree(data.user_id, data.conversation_id)

        if data.settings is not None:

            if "wcd_url" in data.settings:
                del data.settings["wcd_url"]

            api_keys = [key for key in data.settings if key.lower().endswith("api_key")]
            for key in api_keys:
                del data.settings[key]

            tree.configure(**data.settings)

        if data.style is not None:
            tree.change_style(data.style)

        if data.agent_description is not None:
            tree.change_agent_description(data.agent_description)

        if data.end_goal is not None:
            tree.change_end_goal(data.end_goal)

        if data.branch_initialisation is not None:
            tree.set_branch_initialisation(data.branch_initialisation)

        config = Config(
            settings=tree.settings.to_json(),
            style=tree.tree_data.atlas.style,
            agent_description=tree.tree_data.atlas.agent_description,
            end_goal=tree.tree_data.atlas.end_goal,
            branch_initialisation=tree.branch_initialisation,
        )

    except Exception as e:
        logger.exception(f"Error in /change_config_tree API")
        return JSONResponse(content={"error": str(e), "config": {}})

    return JSONResponse(content={"error": "", "config": config.model_dump()})


@router.post("/save")
async def save_config(
    data: SaveConfigData, user_manager: UserManager = Depends(get_user_manager)
):
    """
    Save a config to the weaviate database.
    If the collection ELYSIA_CONFIG__ does not exist, it will be created.

    Args:
        data (SaveConfigData): A class with the following attributes:
            user_id (str): Required. The user ID.
            config_id (str): Required. The ID of the config to save. Can be a user submitted name.
            config (Config): Required. The config to save.
        user_manager (UserManager): The user manager instance.

    Returns:
        JSONResponse: A JSON response with the following attributes:
            error (str): An error message. Empty if no error.
            config (dict): A dictionary of the updated config values.
    """

    logger.debug(f"/save_config API request received")
    logger.debug(f"User ID: {data.user_id}")
    logger.debug(f"Config ID: {data.config_id}")
    logger.debug(f"Config: {data.config}")

    try:
        # Retrieve the user info
        user = await user_manager.get_user_local(data.user_id)
        client_manager: ClientManager = user["client_manager"]

        uuid = generate_uuid5(data.config_id)
        async with client_manager.connect_to_async_client() as client:

            # Create a collection if it doesn't exist
            if await client.collections.exists("ELYSIA_CONFIG__"):
                collection = client.collections.get("ELYSIA_CONFIG__")
            else:
                collection = await client.collections.create(
                    "ELYSIA_CONFIG__",
                    vectorizer_config=wc.Configure.Vectorizer.none(),
                )

            config_item = data.config.model_dump()
            format_dict_to_serialisable(config_item)

            if await collection.data.exists(uuid=uuid):
                await collection.data.update(properties=config_item, uuid=uuid)
            else:
                await collection.data.insert(config_item, uuid=uuid)

    except Exception as e:
        logger.exception(f"Error in /save_config API")
        return JSONResponse(content={"error": str(e), "config": {}})

    return JSONResponse(content={"error": "", "config": config_item})


@router.post("/load_user")
async def load_config_user(
    data: LoadConfigUserData, user_manager: UserManager = Depends(get_user_manager)
):
    """
    Load a config from the weaviate database for a user.
    This will set the default config for all new trees associated with the user.
    It will also propagate the config to any trees set with default settings.
    It will not affect trees that have been set up with their own config.

    It will also update the ClientManager to use the new API keys.

    Args:
        data (LoadConfigData): A class with the following attributes:
            user_id (str): The user ID.
            config_id (str): The ID of the config to load. Can be found in the /list_configs API.
            include_atlas (bool): Whether to include the atlas (style, agent_description, end_goal) in the config.
            include_branch_initialisation (bool): Whether to include the branch initialisation in the config.
            include_settings (bool): Whether to include the settings (LM choice, etc.) in the config.
        user_manager (UserManager): The user manager instance.

    Returns:
        JSONResponse: A JSON response with the following attributes:
            error (str): An error message. Empty if no error.
            config (dict): A dictionary of the updated config values.
    """
    logger.debug(f"/load_config_user API request received")
    logger.debug(f"User ID: {data.user_id}")
    logger.debug(f"Config ID: {data.config_id}")

    try:
        # Retrieve the user info
        user = await user_manager.get_user_local(data.user_id)
        tree_manager: TreeManager = user["tree_manager"]
        settings: Settings = tree_manager.settings
        client_manager: ClientManager = user["client_manager"]

        # Retrieve the config from the weaviate database
        uuid = generate_uuid5(data.config_id)
        async with client_manager.connect_to_async_client() as client:
            collection = client.collections.get("ELYSIA_CONFIG__")
            config_item = await collection.query.fetch_object_by_id(uuid=uuid)

        # Load the configs to the current user
        format_dict_to_serialisable(config_item.properties)
        renamed_config = rename_keys(config_item.properties)

        if data.include_settings:
            settings.load_settings(renamed_config["settings"])
            await client_manager.set_keys_from_settings(settings)

        if data.include_atlas:
            tree_manager.change_style(renamed_config["style"])
            tree_manager.change_agent_description(renamed_config["agent_description"])
            tree_manager.change_end_goal(renamed_config["end_goal"])

        if data.include_branch_initialisation:
            tree_manager.change_branch_initialisation(
                renamed_config["branch_initialisation"]
            )

    except Exception as e:
        logger.exception(f"Error in /load_config API")
        return JSONResponse(content={"error": str(e), "config": {}})

    return JSONResponse(content={"error": "", "config": renamed_config})


@router.post("/load_tree")
async def load_config_tree(
    data: LoadConfigTreeData, user_manager: UserManager = Depends(get_user_manager)
):
    """
    Load a config from the weaviate database for a single tree / conversation.
    This will set the config for the current tree.
    It will not affect other trees associated with the user.

    It will NOT update the ClientManager to use the new API keys.

    Args:
        data (LoadConfigData): A class with the following attributes:
            user_id (str): The user ID.
            conversation_id (str): The conversation ID.
            config_id (str): The ID of the config to load. Can be found in the /list_configs API.
            include_atlas (bool): Whether to include the atlas (style, agent_description, end_goal) in the config.
            include_branch_initialisation (bool): Whether to include the branch initialisation in the config.
            include_settings (bool): Whether to include the settings (LM choice, etc.) in the config.
        user_manager (UserManager): The user manager instance.

    Returns:
        JSONResponse: A JSON response with the following attributes:
            error (str): An error message. Empty if no error.
            config (dict): A dictionary of the updated config values.
    """
    logger.debug(f"/load_config_tree API request received")
    logger.debug(f"User ID: {data.user_id}")
    logger.debug(f"Conversation ID: {data.conversation_id}")
    logger.debug(f"Config ID: {data.config_id}")

    try:
        # Retrieve the user info
        user = await user_manager.get_user_local(data.user_id)
        tree: Tree = await user_manager.get_tree(data.user_id, data.conversation_id)
        client_manager: ClientManager = user["client_manager"]

        # Retrieve the config from the weaviate database
        uuid = generate_uuid5(data.config_id)
        async with client_manager.connect_to_async_client() as client:
            collection = client.collections.get("ELYSIA_CONFIG__")
            config_item = await collection.query.fetch_object_by_id(uuid=uuid)

        # Load the configs to the current user
        format_dict_to_serialisable(config_item.properties)
        renamed_config = rename_keys(config_item.properties)

        if data.include_settings:
            tree.configure(
                **{
                    c: renamed_config["settings"][c]
                    for c in renamed_config["settings"]
                    if (c != "api_keys" and not c.endswith("api_key"))
                }
            )

        if data.include_atlas:
            tree.change_style(renamed_config["style"])
            tree.change_agent_description(renamed_config["agent_description"])
            tree.change_end_goal(renamed_config["end_goal"])

        if data.include_branch_initialisation:
            tree.set_branch_initialisation(renamed_config["branch_initialisation"])

    except Exception as e:
        logger.exception(f"Error in /load_config API")
        return JSONResponse(content={"error": str(e), "config": {}})

    return JSONResponse(content={"error": "", "config": renamed_config})


@router.post("/list")
async def list_configs(
    data: ListConfigsData, user_manager: UserManager = Depends(get_user_manager)
):
    """
    List all the configs for a user.

    Args:
        data (ListConfigsData): A class with the following attributes:
            user_id (str): The user ID.
        user_manager (UserManager): The user manager instance.

    Returns:
        JSONResponse: A JSON response with the following attributes:
            error (str): An error message. Empty if no error.
            configs (list): A list of config IDs.
    """
    logger.debug(f"/list_configs API request received")
    logger.debug(f"User ID: {data.user_id}")

    try:
        user = await user_manager.get_user_local(data.user_id)
        client_manager: ClientManager = user["client_manager"]

        async with client_manager.connect_to_async_client() as client:

            collection = client.collections.get("ELYSIA_CONFIG__")

            len_collection = await collection.aggregate.over_all(total_count=True)
            len_collection = len_collection.total_count

            response = await collection.query.fetch_objects(limit=len_collection)
            configs = [obj.properties["config_id"] for obj in response.objects]

    except Exception as e:
        logger.exception(f"Error in /list_configs API")
        return JSONResponse(content={"error": str(e), "configs": []})

    return JSONResponse(content={"error": "", "configs": configs})
