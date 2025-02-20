import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from tagflow import DocumentMiddleware, TagResponse, tag, text

from yap.base import (
    IMAGE_DIR,
    create_tables,
)
from yap.claude import generate_modified_prompt
from yap.model import (
    create_pending_generation,
    get_generation_by_id,
    get_image_count,
    get_paginated_images,
    get_prompt_by_uuid,
    mark_stale_generations_as_error,
)
from yap.replicate import generate_image
from yap.view import (
    generate_gallery,
    render_base_layout,
    render_prompt_form,
    render_single_image,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Start background task
    cleanup_task = asyncio.create_task(cleanup_stale_generations())
    yield
    # Cancel background task on shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Yap", default_response_class=TagResponse, lifespan=lifespan)
app.add_middleware(DocumentMiddleware)

create_tables()

app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")


@app.get("/")
def index():
    """Serve the main page with prompt form and image gallery."""
    with render_base_layout():
        render_prompt_form()
        gallery(1)


@app.get("/gallery")
def gallery(page: int = 1):
    """Return just the gallery HTML for HTMX requests."""
    # Set page size
    page_size = 50

    # Get total count of images
    total_count = get_image_count()
    total_pages = (total_count + page_size - 1) // page_size

    # Ensure page is within valid range
    page = max(1, min(page, total_pages))

    # Calculate offset
    offset = (page - 1) * page_size

    # Fetch paginated images from DB (newest first)
    rows = get_paginated_images(page_size, offset)

    generate_gallery(rows, page, total_pages)


@app.post("/generate")
async def generate(
    request: Request,
    aspect_ratio: str = Form("1:1"),
    model: str = Form("black-forest-labs/flux-1.1-pro-ultra"),
    style: str = Form("natural"),
):
    """Handle prompt submission, create a pending record, and start generation in background."""
    # Get all prompt parts from form data
    form_data = await request.form()
    prompt_parts = [
        value.strip()
        for key, value in form_data.items()
        if key.startswith("prompt_part_") and value.strip()
    ]

    # Join parts with commas
    prompt = ", ".join(prompt_parts)

    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)

    generation_id = str(uuid.uuid4())

    # Create pending record
    create_pending_generation(generation_id, prompt, model, aspect_ratio)

    # Start background task
    asyncio.create_task(
        generate_image(generation_id, prompt, aspect_ratio, model, style)
    )

    row = get_generation_by_id(generation_id)
    return render_single_image(*row)


@app.get("/check/{generation_id}")
async def check_status(generation_id: str):
    """Check the status of a specific generation and return updated markup."""
    row = get_generation_by_id(generation_id)

    if not row:
        with tag.div():
            text("Generation not found")
    else:
        return render_single_image(*row)


@app.post("/add-prompt-part")
async def add_prompt_part(request: Request):
    """Add a prompt part to the prompt form."""
    form_data = await request.form()
    part = form_data.get("text")
    previous_parts = []
    for key, value in form_data.items():
        if key.startswith("prompt_part_"):
            previous_parts.append(value)

    prompt = ", ".join(previous_parts) + ", " + part

    return render_prompt_form(prompt)


@app.post("/modify-prompt")
async def modify_prompt(request: Request, modification: str = Form(...)):
    """Use Claude to modify the prompt based on the user's request."""
    try:
        # Get all prompt parts from form data
        form_data = await request.form()
        prompt_parts = [
            value.strip()
            for key, value in form_data.items()
            if key.startswith("prompt_part_") and value.strip()
        ]

        # Join parts with commas for the original prompt
        prompt = ", ".join(prompt_parts)

        if not prompt:
            return render_prompt_form()

        modified_prompt = await generate_modified_prompt(modification, prompt)

        if modified_prompt:
            return render_prompt_form(modified_prompt)
        else:
            print("No modified prompt found")
            return render_prompt_form(prompt)

    except Exception as e:
        print(f"Error modifying prompt: {e}")
        return render_prompt_form(prompt)


@app.post("/copy-prompt/{uuid_str}")
async def copy_prompt(uuid_str: str):
    """Get the prompt for an image and return a new form with it."""
    prompt = get_prompt_by_uuid(uuid_str)
    if prompt:
        return render_prompt_form(prompt)
    return render_prompt_form()


async def cleanup_stale_generations():
    """Background task to clean up stale pending generations."""
    while True:
        try:
            mark_stale_generations_as_error()
            # Wait for 5 minutes before next check
            await asyncio.sleep(300)
        except Exception as e:
            print(f"Error cleaning up stale generations: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying if there's an error
