import asyncio
import logging
import os
import re
import uuid
from typing import Optional

from fastapi import Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from tagflow import DocumentMiddleware, tag, text

from slopbox.base import (
    IMAGE_DIR,
    conn,
)
from slopbox.claude import generate_modified_prompt
from slopbox.fastapi import app

# Import the new genimg module
from slopbox.genimg import generate_image
from slopbox.image import (
    render_image_gallery,
    render_image_or_status,
    render_slideshow,
    render_slideshow_content,
    render_spec_block,
)
from slopbox.model import (
    create_pending_generation,
    get_gallery_total_pages,
    get_generation_by_id,
    get_paginated_specs_with_images,
    get_prompt_by_uuid,
    get_random_liked_image,
    get_random_spec_image,
    get_random_weighted_image,
    toggle_like,
)
from slopbox.pageant import pageant, pageant_choose
from slopbox.prompt.form import render_prompt_form_content, render_prompt_part_input
from slopbox.ui import render_base_layout

app.add_middleware(DocumentMiddleware)

app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")


@app.get("/")
async def index(request: Request):
    """Serve the main page with prompt form and image gallery."""
    return await gallery(request)  # Just redirect to gallery view


@app.get("/gallery")
async def gallery(
    request: Request,
    page: int = 1,
    sort_by: str = "recency",
    liked_only: bool = False,
):
    """Show the gallery page."""
    # Each page represents one day
    page_size = 1  # one day per page
    offset = page - 1  # offset in days

    # Get specs and their images for this day
    specs_with_images = get_paginated_specs_with_images(
        page_size, offset, sort_by, liked_only
    )

    # Get total pages
    total_pages = get_gallery_total_pages(liked_only)

    if request.headers.get("HX-Request"):
        return render_image_gallery(
            specs_with_images, page, total_pages, sort_by, liked_only=liked_only
        )

    # Return the gallery content
    with render_base_layout():
        render_image_gallery(
            specs_with_images, page, total_pages, sort_by, liked_only=liked_only
        )


@app.post("/generate")
async def generate(
    request: Request,
    aspect_ratio: str = Form("1:1"),
    model: str = Form("black-forest-labs/flux-1.1-pro-ultra"),
    style: str = Form("realistic_image/natural_light"),
):
    # Get all prompt parts from form data
    form_data = await request.form()
    prompt_parts = [
        value.strip()
        for key, value in form_data.items()
        if key.startswith("prompt_part_") and isinstance(value, str) and value.strip()
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
    create_pending_generation(generation_id, prompt, model, aspect_ratio, style)

    # Start background task
    asyncio.create_task(
        generate_image(generation_id, prompt, aspect_ratio, model, style)
    )

    image = get_generation_by_id(generation_id)
    assert image is not None
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
        render_image_or_status(image)


@app.post("/add-prompt-part")
async def add_prompt_part(request: Request):
    """Add a prompt part to the prompt form."""
    form_data = await request.form()
    part = form_data.get("text", "")
    assert isinstance(part, str)

    previous_parts = [
        value.strip()
        for key, value in form_data.items()
        if key.startswith("prompt_part_") and isinstance(value, str) and value.strip()
    ]

    all_parts = previous_parts + [part]

    # Check if we're dealing with sentences (any part ends with period + space)
    if any(re.search(r"\.(?:\s+|\n+)", p + " ") for p in all_parts):
        prompt = " ".join(all_parts)  # Join with spaces for sentences
    else:
        prompt = ", ".join(all_parts)  # Join with commas for non-sentences

    return render_prompt_form_content(prompt)


@app.post("/modify-prompt")
async def modify_prompt(request: Request, modification: str = Form(...)):
    """Use Claude to modify the prompt based on the user's request."""
    try:
        # Get all prompt parts from form data
        form_data = await request.form()
        prompt_parts = [
            value.strip()
            for key, value in form_data.items()
            if key.startswith("prompt_part_")
            and isinstance(value, str)
            and value.strip()
        ]

        # Join parts with commas for the original prompt
        prompt = ", ".join(prompt_parts)

        if not prompt:
            return render_prompt_form_content()

        modified_prompt = await generate_modified_prompt(modification, prompt)

        if modified_prompt:
            return render_prompt_form_content(modified_prompt)
        else:
            print("No modified prompt found")
            return render_prompt_form_content(prompt)

    except Exception as e:
        print(f"Error modifying prompt: {e}")
        return render_prompt_form_content(prompt)


@app.post("/copy-prompt/{uuid_str}")
async def copy_prompt(uuid_str: str):
    """Get the prompt for an image and return a new form with it."""
    prompt = get_prompt_by_uuid(uuid_str)
    if prompt:
        return render_prompt_form_content(prompt)
    return render_prompt_form_content()


@app.post("/regenerate/{spec_id}")
async def regenerate(spec_id: int, style: str = Form("realistic_image/natural_light")):
    """Create a new generation using an existing image spec."""
    generation_id = str(uuid.uuid4())

    # Get the spec details from the database
    with conn:
        cur = conn.execute(
            """
            SELECT prompt, model, aspect_ratio, style
            FROM image_specs
            WHERE id = ?
            """,
            (spec_id,),
        )
        row = cur.fetchone()
        if not row:
            return JSONResponse({"error": "Spec not found"}, status_code=404)

        prompt, model, aspect_ratio, style = row

    # Create pending record
    create_pending_generation(generation_id, prompt, model, aspect_ratio, style)

    # Start background task
    asyncio.create_task(
        generate_image(generation_id, prompt, aspect_ratio, model, style)
    )

    image = get_generation_by_id(generation_id)
    assert image is not None
    # Just render the image status without the prompt info
    render_image_or_status(image)


@app.post("/regenerate-8x/{spec_id}")
async def regenerate_8x(
    spec_id: int, style: str = Form("realistic_image/natural_light")
):
    """Create 8 new generations using an existing image spec."""
    # Get the spec details from the database
    with conn:
        cur = conn.execute(
            """
            SELECT prompt, model, aspect_ratio, style
            FROM image_specs
            WHERE id = ?
            """,
            (spec_id,),
        )
        row = cur.fetchone()
        if not row:
            return JSONResponse({"error": "Spec not found"}, status_code=404)

        prompt, model, aspect_ratio, style = row

    # Create 8 pending records and start 8 background tasks
    images_to_render = []
    for _ in range(8):
        generation_id = str(uuid.uuid4())

        # Create pending record
        create_pending_generation(generation_id, prompt, model, aspect_ratio, style)

        # Start background task
        asyncio.create_task(
            generate_image(generation_id, prompt, aspect_ratio, model, style)
        )

        image = get_generation_by_id(generation_id)
        assert image is not None
        images_to_render.append(image)

    # Render all 8 images
    for image in images_to_render:
        render_image_or_status(image)


@app.post("/copy-spec/{spec_id}")
async def copy_spec(spec_id: int):
    """Get the spec details and return a new form with them."""
    with conn:
        cur = conn.execute(
            """
            SELECT prompt, model, aspect_ratio, style
            FROM image_specs
            WHERE id = ?
            """,
            (spec_id,),
        )
        row = cur.fetchone()
        if row:
            prompt, model, aspect_ratio, style = row
            return render_prompt_form_content(prompt, model, aspect_ratio, style)
    return render_prompt_form_content()


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
def slideshow_next(
    spec_id: Optional[int] = None,
):
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
        render_slideshow(image, image_count, liked_only=True)


@app.get("/slideshow/liked/next")
def slideshow_liked_next():
    """Return the next random liked image for the slideshow."""
    image, image_count = get_random_liked_image()
    render_slideshow_content(image, image_count, liked_only=True)


@app.post("/toggle-like/{image_uuid}")
async def toggle_like_endpoint(image_uuid: str):
    """Toggle like status for an image."""
    new_liked_status = toggle_like(image_uuid)

    # Return the updated like indicator
    with tag.div(
        "absolute top-2 right-2 p-2 rounded-full",
        "bg-amber-100 text-amber-600"
        if new_liked_status
        else "bg-white/80 text-neutral-600",
        "opacity-0 group-hover:opacity-100 transition-opacity",
        "z-20 pointer-events-none",
        id=f"like-indicator-{image_uuid}",
    ):
        with tag.span("text-xl"):
            text("♥")


@app.get("/prompt-part/{index}")
async def get_prompt_part(index: int):
    """Return markup for a new prompt part input."""
    return render_prompt_part_input(index)


@app.get("/pageant")
async def pageant_route(request: Request):
    """Show the pageant page with a random pair of images."""
    return await pageant()


@app.post("/pageant/choose/{winner_uuid}/{loser_uuid}")
async def pageant_choose_route(winner_uuid: str, loser_uuid: str):
    """Record a comparison result and return a new pair of images."""
    return await pageant_choose(winner_uuid, loser_uuid)


@app.post("/delete-unliked-images")
async def delete_unliked_images():
    logger = logging.getLogger(__name__)

    deleted_images = 0
    deleted_specs = 0
    deleted_files = 0
    orphaned_files = 0

    with conn:
        # First, get all complete images that are not liked
        cur = conn.execute(
            """
            SELECT i.id, i.uuid, i.filepath, i.spec_id
            FROM images_v3 i
            WHERE i.status = 'complete'
            AND NOT EXISTS (
                SELECT 1 FROM likes WHERE image_uuid = i.uuid
            )
            """
        )

        unliked_images = cur.fetchall()

        # Delete each image file from the file system
        for _, uuid, filepath, _ in unliked_images:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    deleted_files += 1
                except Exception as e:
                    logger.error(f"Failed to delete file {filepath}: {e}")

        # Delete the unliked images from the database
        if unliked_images:
            image_ids = [img[0] for img in unliked_images]
            placeholders = ",".join("?" * len(image_ids))

            conn.execute(
                f"DELETE FROM images_v3 WHERE id IN ({placeholders})", image_ids
            )
            deleted_images = len(image_ids)

        # Now find and delete empty specs (specs with no images)
        cur = conn.execute(
            """
            DELETE FROM image_specs
            WHERE NOT EXISTS (
                SELECT 1 FROM images_v3 WHERE spec_id = image_specs.id
            )
            """
        )
        deleted_specs = cur.rowcount

        # Get all filepaths of liked images to know what to keep
        cur = conn.execute(
            """
            SELECT i.filepath
            FROM images_v3 i
            JOIN likes l ON i.uuid = l.image_uuid
            WHERE i.status = 'complete' AND i.filepath IS NOT NULL
            """
        )
        liked_filepaths = {os.path.basename(row[0]) for row in cur.fetchall() if row[0]}

        # Scan the image directory and delete any files not in the liked_filepaths set
        for filename in os.listdir(IMAGE_DIR):
            if filename.endswith(".png") and filename not in liked_filepaths:
                try:
                    os.remove(os.path.join(IMAGE_DIR, filename))
                    orphaned_files += 1
                except Exception as e:
                    logger.error(f"Failed to delete orphaned file {filename}: {e}")

    # Return a summary of the operation
    with tag.div("p-4 bg-green-100 rounded-md"):
        with tag.h2("text-xl font-bold mb-2"):
            text("Cleanup Complete")

        with tag.ul("list-disc pl-5"):
            with tag.li():
                text(f"Deleted {deleted_images} unliked images from database")
            with tag.li():
                text(f"Deleted {deleted_files} image files from disk")
            with tag.li():
                text(f"Deleted {orphaned_files} orphaned files from disk")
            with tag.li():
                text(f"Removed {deleted_specs} empty image specs")
