import gc
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from elysia.api.core.log import logger, set_log_level
from elysia.api.dependencies.common import get_user_manager
from elysia.api.middleware.error_handlers import register_error_handlers
from elysia.api.routes import (
    collections,
    config,
    feedback,
    init,
    processor,
    query,
    utils,
)
from elysia.api.services.user import UserManager
from elysia.api.utils.resources import print_resources


from pathlib import Path


async def perform_garbage_collection():
    gc.collect(generation=2)


async def check_timeouts():
    user_manager = get_user_manager()
    await user_manager.check_all_trees_timeout()


async def output_resources():
    user_manager = get_user_manager()
    await print_resources(user_manager, save_to_file=True)


async def check_restart_clients():
    user_manager = get_user_manager()
    await user_manager.check_restart_clients()


@asynccontextmanager
async def lifespan(app: FastAPI):
    user_manager = get_user_manager()

    scheduler = AsyncIOScheduler()
    set_log_level("DEBUG")  # TODO: change to WARNING if in prod

    # use prime numbers for intervals so they don't overlap
    scheduler.add_job(perform_garbage_collection, "interval", seconds=23)
    scheduler.add_job(check_timeouts, "interval", seconds=29)
    scheduler.add_job(check_restart_clients, "interval", seconds=31)
    scheduler.add_job(output_resources, "interval", seconds=1103)

    scheduler.start()
    yield
    scheduler.shutdown()

    await user_manager.close_all_clients()


# Create FastAPI app instance
app = FastAPI(title="Elysia API", version="0.3.0", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register error handlers
register_error_handlers(app)

# Include routers
app.include_router(init.router, prefix="/init", tags=["init"])
app.include_router(query.router, prefix="/ws", tags=["websockets"])
app.include_router(processor.router, prefix="/ws", tags=["websockets"])
app.include_router(collections.router, prefix="/collections", tags=["collections"])
app.include_router(config.router, prefix="/config", tags=["config"])
app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
app.include_router(utils.router, prefix="/util", tags=["utilities"])


# Health check endpoint (kept in main app.py due to its simplicity)
@app.get("/api/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    return {"status": "healthy"}


# Mount the app from static files
# BASE_DIR = Path(__file__).resolve().parent

# # Serve the assets (JS, CSS, images, etc.)
# app.mount(
#     "/static/_next",
#     StaticFiles(directory=BASE_DIR / "static/_next"),
#     name="next-assets",
# )

# # Serve the main page and other static files
# app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="app")


# @app.get("/")
# @app.head("/")
# async def serve_frontend():
#     return FileResponse(os.path.join(BASE_DIR, "static/index.html"))
