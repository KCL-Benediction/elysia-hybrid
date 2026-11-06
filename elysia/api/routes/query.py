import asyncio

from fastapi import APIRouter, Depends, WebSocket
from starlette.websockets import WebSocketDisconnect

from elysia.api.core.log import logger
from elysia.api.dependencies.common import get_user_manager
from elysia.api.services.user import UserManager
from elysia.api.utils.websocket import help_websocket
from elysia.objects import Error
from elysia.util.collection import retrieve_all_collection_names

router = APIRouter()


async def process(data: dict, websocket: WebSocket, user_manager: UserManager):
    logger.debug(f"/query API request received")
    logger.debug(f"User ID: {data['user_id']}")
    logger.debug(f"Conversation ID: {data['conversation_id']}")
    logger.debug(f"Query: {data['query']}")
    logger.debug(f"Query ID: {data['query_id']}")
    logger.debug(f"Training route: {data['route']}")
    logger.debug(f"Training mimick model: {data['mimick']}")
    logger.debug(f"Collection names: {data['collection_names']}")

    try:
        # optional arguments
        if "route" in data:
            route = data["route"]
        else:
            route = None

        async for yielded_result in user_manager.process_tree(
            user_id=data["user_id"],
            conversation_id=data["conversation_id"],
            query=data["query"],
            query_id=data["query_id"],
            training_route=route,
            collection_names=data["collection_names"],
        ):
            if asyncio.iscoroutine(yielded_result):
                yielded_result = await yielded_result
            try:
                if (
                    yielded_result is not None
                    and "type" in yielded_result
                    and yielded_result["type"] != "training_update"
                    and yielded_result["type"] != "timer"
                ):
                    await websocket.send_json(yielded_result)
            except WebSocketDisconnect:
                logger.info("Client disconnected during processing")
                break
            # Add a small delay between messages to prevent overwhelming
            await asyncio.sleep(0.005)

    except Exception as e:
        logger.exception(f"Error in /query API")

        if "conversation_id" in data:
            error = Error(text=f"{str(e)}")
            error_payload = await error.to_frontend(
                data["conversation_id"], data["query_id"]
            )
            await websocket.send_json(error_payload)
        else:
            error_payload = await Error(text=f"{str(e)}").to_frontend(
                "", data["query_id"]
            )
            await websocket.send_json(error_payload)


# Process endpoint
@router.websocket("/query")
async def query_websocket(
    websocket: WebSocket, user_manager: UserManager = Depends(get_user_manager)
):
    """
    WebSocket endpoint for processing pipelines.
    Handles real-time communication for pipeline execution and status updates.
    """
    await help_websocket(websocket, lambda data, ws: process(data, ws, user_manager))
