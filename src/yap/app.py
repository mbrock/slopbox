import asyncio
import uuid
from contextlib import asynccontextmanager
import re
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from tagflow import DocumentMiddleware, TagResponse, tag, text

from yap.base import (
    IMAGE_DIR,
    conn,
    create_tables,
    migrate_v2_to_v3,
)
from yap.claude import generate_modified_prompt
from yap.model import (
    Image,
    ImageSpec,
    create_pending_generation,
    get_generation_by_id,
    get_paginated_specs_with_images,
    get_prompt_by_uuid,
    get_random_weighted_image,
    get_random_spec_image,
    get_random_liked_image,
    get_spec_count,
    get_spec_generations,
    mark_stale_generations_as_error,
    split_prompt,
    toggle_like,
    update_generation_status,
)
from yap.replicate import generate_image
from yap.view import (
    generate_gallery,
    render_base_layout,
    render_prompt_form,
    render_single_image,
    render_image_or_status,
    render_spec_block,
    render_slideshow,
    render_slideshow_content,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
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


app = FastAPI(title="Yap", default_response_class=TagResponse, lifespan=lifespan)
app.add_middleware(DocumentMiddleware)

app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")


@app.get("/")
async def index(request: Request):
    """Serve the main page with prompt form and image gallery."""
    with render_base_layout():
        render_prompt_form()
        await gallery(request)


@app.get("/gallery")
async def gallery(
    request: Request,
    page: int = 1,
    sort_by: str = "recency",
    min_images: int = 0,
    liked_only: bool = False,
):
    """Show the gallery page."""
    page_size = 10
    offset = (page - 1) * page_size

    # Get specs and their images
    specs_with_images = get_paginated_specs_with_images(
        page_size, offset, sort_by, min_images, liked_only
    )

    # Calculate total pages
    total_specs = get_spec_count()
    total_pages = (total_specs + page_size - 1) // page_size

    # If it's an HTMX request, just return the gallery content
    # if request.headers.get("HX-Request"):
    return generate_gallery(
        specs_with_images, page, total_pages, sort_by, min_images, liked_only
    )

    # # Otherwise return the full page
    # with render_base_layout():
    #     with tag.div(classes="flex flex-col w-full"):
    #         render_prompt_form()
    #         generate_gallery(
    #             specs_with_images, page, total_pages, sort_by, min_images, liked_only
    #         )


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

    # Check if we're dealing with sentences (any part ends with period + space)
    if any(re.search(r"\.(?:\s+|\n+)", part + " ") for part in prompt_parts):
        prompt = " ".join(prompt_parts)  # Join with spaces for sentences
    else:
        prompt = ", ".join(prompt_parts)  # Join with commas for non-sentences

    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)

    generation_id = str(uuid.uuid4())

    # Create pending record
    create_pending_generation(generation_id, prompt, model, aspect_ratio)

    # Start background task
    asyncio.create_task(
        generate_image(generation_id, prompt, aspect_ratio, model, style)
    )

    image = get_generation_by_id(generation_id)
    # Return a complete spec block for this new image
    render_spec_block(image.spec, [image])


@app.get("/check/{generation_id}")
async def check_status(generation_id: str):
    """Check the status of a specific generation and return updated markup."""
    image = get_generation_by_id(generation_id)

    if not image:
        with tag.div():
            text("Generation not found")
    else:
        # Just render the image status without the prompt info
        with tag.div(classes="relative"):
            render_image_or_status(image)


@app.post("/add-prompt-part")
async def add_prompt_part(request: Request):
    """Add a prompt part to the prompt form."""
    form_data = await request.form()
    part = form_data.get("text", "").strip()
    previous_parts = [
        value.strip()
        for key, value in form_data.items()
        if key.startswith("prompt_part_") and value.strip()
    ]

    all_parts = previous_parts + [part]

    # Check if we're dealing with sentences (any part ends with period + space)
    if any(re.search(r"\.(?:\s+|\n+)", p + " ") for p in all_parts):
        prompt = " ".join(all_parts)  # Join with spaces for sentences
    else:
        prompt = ", ".join(all_parts)  # Join with commas for non-sentences

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


@app.post("/regenerate/{spec_id}")
async def regenerate(spec_id: int):
    """Create a new generation using an existing image spec."""
    generation_id = str(uuid.uuid4())

    # Get the spec details from the database
    with conn:
        cur = conn.execute(
            """
            SELECT prompt, model, aspect_ratio
            FROM image_specs
            WHERE id = ?
            """,
            (spec_id,),
        )
        row = cur.fetchone()
        if not row:
            return JSONResponse({"error": "Spec not found"}, status_code=404)

        prompt, model, aspect_ratio = row

    # Create pending record
    create_pending_generation(generation_id, prompt, model, aspect_ratio)

    # Start background task
    asyncio.create_task(
        generate_image(generation_id, prompt, aspect_ratio, model, "natural")
    )

    image = get_generation_by_id(generation_id)
    # Just render the image status without the prompt info
    with tag.div(classes="relative"):
        render_image_or_status(image)


@app.post("/copy-spec/{spec_id}")
async def copy_spec(spec_id: int):
    """Get the spec details and return a new form with them."""
    with conn:
        cur = conn.execute(
            """
            SELECT prompt, model, aspect_ratio
            FROM image_specs
            WHERE id = ?
            """,
            (spec_id,),
        )
        row = cur.fetchone()
        if row:
            prompt, model, aspect_ratio = row
            return render_prompt_form(prompt, model, aspect_ratio)
    return render_prompt_form()


@app.get("/slideshow")
def slideshow(spec_id: Optional[int] = None):
    """Serve the slideshow page."""
    print(f"Slideshow requested with spec_id: {spec_id}")
    if spec_id is not None:
        image, image_count = get_random_spec_image(spec_id)
    else:
        image, image_count = get_random_weighted_image()
    with render_base_layout():
        render_slideshow(image, image_count, spec_id)


@app.get("/slideshow/next")
def slideshow_next(spec_id: Optional[int] = None):
    """Return the next random image for the slideshow."""
    print(f"Slideshow next requested with spec_id: {spec_id}")
    if spec_id is not None:
        image, image_count = get_random_spec_image(spec_id)
    else:
        image, image_count = get_random_weighted_image()
    render_slideshow_content(image, image_count, spec_id)


@app.get("/slideshow/liked")
def slideshow_liked():
    """Serve the slideshow page for liked images."""
    image, image_count = get_random_liked_image()
    with render_base_layout():
        render_slideshow(image, image_count)


@app.get("/slideshow/liked/next")
def slideshow_liked_next():
    """Return the next random liked image for the slideshow."""
    image, image_count = get_random_liked_image()
    render_slideshow_content(image, image_count)


@app.post("/toggle-like/{image_uuid}")
async def toggle_like_endpoint(image_uuid: str):
    """Toggle like status for an image."""
    new_liked_status = toggle_like(image_uuid)

    # Return the updated like indicator
    with tag.div(
        id=f"like-indicator-{image_uuid}",
        classes=f"absolute top-2 right-2 p-2 rounded-full {'bg-amber-100 text-amber-600' if new_liked_status else 'bg-white/80 text-neutral-600'} opacity-0 group-hover:opacity-100 transition-opacity z-20 pointer-events-none",
    ):
        with tag.span(classes="text-xl"):
            text("♥")


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
