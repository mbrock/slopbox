import asyncio
import os
import uuid
from contextlib import asynccontextmanager

import aiofiles
import anthropic
import replicate
from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from tagflow import DocumentMiddleware, TagResponse, tag, text

from yap.base import (
    ASPECT_TO_RECRAFT,
    IMAGE_DIR,
    conn,
    create_tables,
    prompt_modification_system_message,
)
from yap.views import (
    generate_gallery,
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


# Initialize FastAPI with TagFlow integration and lifespan
app = FastAPI(title="Yap", default_response_class=TagResponse, lifespan=lifespan)
app.add_middleware(DocumentMiddleware)

# Initialize Anthropic client
claude = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

create_tables()

# Mount the image directory as static files for serving images
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")


# Style components for consistent UI
@app.post("/add-prompt-part", response_class=TagResponse)
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


@app.get("/gallery", response_class=TagResponse)
async def gallery(page: int = 1):
    """Return just the gallery HTML for HTMX requests."""
    # Set page size
    page_size = 50

    # Get total count of images
    with conn:
        cur = conn.execute("SELECT COUNT(*) FROM images_v2")
        total_count = cur.fetchone()[0]
        total_pages = (total_count + page_size - 1) // page_size

        # Ensure page is within valid range
        page = max(1, min(page, total_pages))

        # Calculate offset
        offset = (page - 1) * page_size

        # Fetch paginated images from DB (newest first)
        cur = conn.execute(
            "SELECT prompt, filepath, status, uuid FROM images_v2 ORDER BY id DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        )

        rows = cur.fetchall()

    generate_gallery(rows, page, total_pages)


@app.get("/", response_class=TagResponse)
async def index():
    """Serve the main page with prompt form and image gallery."""
    # Build full HTML page
    with tag.html(lang="en"):
        with tag.head():
            with tag.title():
                text("Yap")
            add_external_scripts()
        with tag.body(classes="bg-neutral-400 flex gap-4 h-screen"):
            render_prompt_form()
            await gallery(1)


def add_external_scripts():
    with tag.script(src="https://unpkg.com/@tailwindcss/browser@4"):
        pass
    with tag.script(src="https://unpkg.com/htmx.org@2.0.4"):
        pass


@app.post("/generate", response_class=TagResponse)
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
    with conn:
        conn.execute(
            "INSERT INTO images_v2 (uuid, prompt, status, model, aspect_ratio) VALUES (?, ?, ?, ?, ?)",
            (generation_id, prompt, "pending", model, aspect_ratio),
        )

        # Start background task
        asyncio.create_task(
            generate_image(generation_id, prompt, aspect_ratio, model, style)
        )

        cur = conn.execute(
            "SELECT prompt, filepath, status, uuid FROM images_v2 WHERE uuid = ?",
            (generation_id,),
        )

        row = cur.fetchone()

        return render_single_image(*row)


async def generate_image(
    generation_id: str, prompt: str, aspect_ratio: str, model: str, style: str
):
    """Background task to generate the image and update the database."""
    try:
        # Set up model inputs
        model_inputs = {
            "prompt": prompt,
            "disable_safety_checker": True,
            "output_format": "png",
            "raw": True,
        }

        # Handle model-specific parameters
        if "recraft" in model:
            model_inputs["size"] = ASPECT_TO_RECRAFT[aspect_ratio]
            style_map = {
                "natural": "realistic_image/natural_light",
                "studio": "realistic_image/studio_portrait",
                "flash": "realistic_image/hard_flash",
                "illustration": "digital_illustration/grain",
            }
            model_inputs["style"] = style_map.get(
                style, "realistic_image/natural_light"
            )
        else:
            model_inputs["aspect_ratio"] = aspect_ratio
            model_inputs["safety_tolerance"] = 6

        # Generate the image
        output = await replicate.async_run(
            model,
            input=model_inputs,
        )

        # Read the image bytes
        if isinstance(output, list):
            image_bytes = await output[0].aread()
        else:
            image_bytes = await output.aread()

        # Save the image
        filename = f"{generation_id}.png"
        file_path = os.path.join(IMAGE_DIR, filename)
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(image_bytes)

        # Update the database
        with conn:
            conn.execute(
                "UPDATE images_v2 SET status = ?, filepath = ? WHERE uuid = ?",
                ("complete", file_path, generation_id),
            )

    except Exception as e:
        print(f"Error generating image: {e}")
        with conn:
            conn.execute(
                "UPDATE images_v2 SET status = ? WHERE uuid = ?",
                ("error", generation_id),
            )


@app.get("/check/{generation_id}", response_class=TagResponse)
async def check_status(generation_id: str):
    """Check the status of a specific generation and return updated markup."""
    with conn:
        cur = conn.execute(
            "SELECT prompt, filepath, status, uuid FROM images_v2 WHERE uuid = ?",
            (generation_id,),
        )
        row = cur.fetchone()

    if not row:
        with tag.div():
            text("Generation not found")
    else:
        return render_single_image(*row)


@app.post("/modify-prompt", response_class=TagResponse)
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


async def generate_modified_prompt(modification, prompt):
    message = await claude.messages.create(
        max_tokens=1024,
        model="claude-3-5-sonnet-latest",
        system=prompt_modification_system_message(),
        messages=[
            {
                "role": "user",
                "content": f"<original-prompt>{prompt}</original-prompt>\n<modification-request>{modification}</modification-request>",
            }
        ],
        tools=[
            {
                "name": "replacePromptText",
                "description": "Replace the original prompt with a modified version based on the modification request",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "modified_prompt": {
                            "type": "string",
                            "description": "The modified version of the original prompt",
                        }
                    },
                    "required": ["modified_prompt"],
                },
            }
        ],
    )

    print(message)

    # Extract the modified prompt from the tool use response
    modified_prompt = None
    for content in message.content:
        if content.type == "tool_use" and content.name == "replacePromptText":
            modified_prompt = content.input["modified_prompt"]
            break
    return modified_prompt


@app.post("/copy-prompt/{uuid_str}", response_class=TagResponse)
async def copy_prompt(uuid_str: str):
    """Get the prompt for an image and return a new form with it."""
    with conn:
        cur = conn.execute("SELECT prompt FROM images_v2 WHERE uuid = ?", (uuid_str,))
        row = cur.fetchone()
        if row:
            return render_prompt_form(row[0])

    return render_prompt_form()


async def cleanup_stale_generations():
    """Background task to clean up stale pending generations."""
    while True:
        try:
            # Find and update stale pending generations (older than 1 hour)
            with conn:
                conn.execute(
                    """
                    UPDATE images_v2 
                    SET status = 'error' 
                    WHERE status = 'pending' 
                    AND datetime(created, '+1 hour') < datetime('now')
                    """
                )

            # Wait for 5 minutes before next check
            await asyncio.sleep(300)
        except Exception as e:
            print(f"Error cleaning up stale generations: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying if there's an error
