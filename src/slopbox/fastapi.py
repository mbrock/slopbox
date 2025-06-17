import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from tagflow import TagResponse

from slopbox.base import create_tables, migrate_v2_to_v3
from slopbox.model import mark_stale_generations_as_error


async def cleanup_stale_generations():
    """Background task to clean up stale pending generations."""
    while True:
        try:
            mark_stale_generations_as_error()
            # Wait for 5 minutes before next check
            await asyncio.sleep(300)
        except Exception as e:
            print(f"Error cleaning up stale generations: {e}")
            await asyncio.sleep(
                60
            )  # Wait a minute before retrying if there's an error


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Check for required API keys
    replicate_key = os.environ.get("REPLICATE_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if not replicate_key:
        raise RuntimeError(
            "REPLICATE_API_KEY environment variable is not set"
        )
    if not anthropic_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set"
        )

    # Create tables and migrate data
    create_tables()
    migrate_v2_to_v3()

    # Start background task
    cleanup_task = asyncio.create_task(cleanup_stale_generations())
    yield
    # Cancel background task on shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Slopbox", default_response_class=TagResponse, lifespan=lifespan
)
