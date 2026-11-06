from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from elysia.api.api_types import InitialiseTreeData, InitialiseUserData, Config
from elysia.api.dependencies.common import get_user_manager
from elysia.api.services.user import UserManager
from elysia.api.core.log import logger
from elysia.config import Settings

router = APIRouter()


@router.post("/user")
async def initialise_user(
    data: InitialiseUserData, user_manager: UserManager = Depends(get_user_manager)
):
    """
    Create a user with a specified config.
    """
    logger.debug(f"/initialise_user API request received")
    logger.debug(f"User ID: {data.user_id}")
    logger.debug(f"Default models: {data.default_models}")
    logger.debug(f"Settings: {data.settings}")
    logger.debug(f"Style: {data.style}")
    logger.debug(f"Agent description: {data.agent_description}")
    logger.debug(f"End goal: {data.end_goal}")
    logger.debug(f"Branch initialisation: {data.branch_initialisation}")

    try:

        settings = Settings()
        settings.set_from_env()
        settings.setup_app_logger(logger)

        if data.settings is not None:
            settings.configure(**data.settings)

        if data.default_models:
            settings.default_models()

        # create a user and set up the config
        user_manager.add_user_local(
            data.user_id,
            style=data.style,
            agent_description=data.agent_description,
            end_goal=data.end_goal,
            branch_initialisation=data.branch_initialisation,
            settings=settings,
        )

        config = Config(
            settings=settings.to_json(),
            style=data.style,
            agent_description=data.agent_description,
            end_goal=data.end_goal,
            branch_initialisation=data.branch_initialisation,
        )

    except Exception as e:
        logger.exception(f"Error in /initialise_user API")
        return JSONResponse(content={"error": str(e), "config": {}}, status_code=500)

    return JSONResponse(
        content={"error": "", "config": config.model_dump()}, status_code=200
    )


@router.post("/tree")
async def initialise_tree(
    data: InitialiseTreeData, user_manager: UserManager = Depends(get_user_manager)
):
    logger.debug(f"/initialise_tree API request received")
    logger.debug(f"User ID: {data.user_id}")
    logger.debug(f"Conversation ID: {data.conversation_id}")
    logger.debug(f"Style: {data.style}")
    logger.debug(f"Agent Description: {data.agent_description}")
    logger.debug(f"End Goal: {data.end_goal}")
    logger.debug(f"Branch Initialisation: {data.branch_initialisation}")
    logger.debug(f"Low Memory: {data.low_memory}")
    logger.debug(f"Settings: {data.settings}")

    try:
        tree = await user_manager.initialise_tree(
            data.user_id,
            data.conversation_id,
            style=data.style,
            agent_description=data.agent_description,
            end_goal=data.end_goal,
            branch_initialisation=data.branch_initialisation,
            low_memory=data.low_memory,
            settings=data.settings,
        )
    except Exception as e:
        logger.exception(f"Error in /initialise_tree API")
        return JSONResponse(
            content={
                "conversation_id": data.conversation_id,
                "tree": "",
                "error": str(e),
            },
            status_code=500,
        )

    return JSONResponse(
        content={
            "conversation_id": data.conversation_id,
            "tree": tree.tree,
            "error": "",
        },
        status_code=200,
    )
