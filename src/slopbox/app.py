import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from typing import Optional

from fastapi import Form, Request, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
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
from slopbox.ui import render_base_layout, Styles

app.add_middleware(DocumentMiddleware)

app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")
app.mount("/static", StaticFiles(directory="static"), name="static")


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


@app.get("/video-sync")
async def video_sync(request: Request):
    """Serve the video-audio synchronization page."""
    if request.headers.get("HX-Request"):
        render_video_sync_content()
    else:
        with render_base_layout():
            render_video_sync_content()


# Global progress tracking
export_progress = {}

@app.post("/export-video-server")
async def export_video_server(
    video_file: UploadFile = File(...),
    audio_file: UploadFile = File(...),
    offset: float = Form(0.0),
    crossfade: float = Form(50.0),
    clip_video: bool = Form(False)
):
    """Start export and return job ID for progress tracking."""
    
    print(f"🔍 DEBUG: Export endpoint called with files: {video_file.filename}, {audio_file.filename}")
    print(f"🔍 DEBUG: Parameters - offset: {offset}, crossfade: {crossfade}, clip_video: {clip_video}")
    print(f"🔍 DEBUG: Video file size: {video_file.size}, content_type: {video_file.content_type}")
    print(f"🔍 DEBUG: Audio file size: {audio_file.size}, content_type: {audio_file.content_type}")
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    print(f"🔍 DEBUG: Generated job ID: {job_id}")
    
    try:
        # Read file contents immediately before they get closed
        print("🔍 DEBUG: Reading video file contents...")
        await video_file.seek(0)
        video_content = await video_file.read()
        print(f"🔍 DEBUG: Read {len(video_content)} bytes from video file")
        
        print("🔍 DEBUG: Reading audio file contents...")
        await audio_file.seek(0)
        audio_content = await audio_file.read()
        print(f"🔍 DEBUG: Read {len(audio_content)} bytes from audio file")
        
    except Exception as e:
        print(f"❌ Error reading uploaded files: {e}")
        return JSONResponse({"error": f"Failed to read uploaded files: {str(e)}"}, status_code=400)
    
    # Initialize progress
    export_progress[job_id] = {
        "status": "initializing",
        "progress": 0,
        "message": "Starting export...",
        "error": None,
        "output_path": None,
        "filename": video_file.filename
    }
    
    # Start background task with file contents
    print(f"🔍 DEBUG: Starting background task for job {job_id}")
    asyncio.create_task(process_video_export_with_content(
        job_id, video_content, audio_content, video_file.filename, audio_file.filename, offset, crossfade, clip_video
    ))
    
    return JSONResponse({"job_id": job_id})


@app.get("/export-progress/{job_id}")
async def get_export_progress(job_id: str):
    """Get export progress via Server-Sent Events."""
    
    async def event_stream():
        while True:
            if job_id not in export_progress:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break
                
            progress_data = export_progress[job_id]
            yield f"data: {json.dumps(progress_data)}\n\n"
            
            # If complete or error, stop streaming
            if progress_data["status"] in ["complete", "error"]:
                break
                
            await asyncio.sleep(1)  # Update every second
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@app.get("/export-download/{job_id}")
async def download_export(job_id: str):
    """Download completed export."""
    
    if job_id not in export_progress:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    
    progress_data = export_progress[job_id]
    
    if progress_data["status"] != "complete":
        return JSONResponse({"error": "Export not complete"}, status_code=400)
    
    output_path = progress_data["output_path"]
    if not output_path or not os.path.exists(output_path):
        return JSONResponse({"error": "Output file not found"}, status_code=404)
    
    filename = f"synced_{progress_data['filename']}"
    
    # Custom FileResponse that cleans up after download
    class CleanupFileResponse(FileResponse):
        def __init__(self, *args, cleanup_path=None, cleanup_dir=None, **kwargs):
            super().__init__(*args, **kwargs)
            self.cleanup_path = cleanup_path
            self.cleanup_dir = cleanup_dir
        
        async def __call__(self, scope, receive, send):
            try:
                await super().__call__(scope, receive, send)
            finally:
                # Clean up after file is sent
                try:
                    if self.cleanup_path and os.path.exists(self.cleanup_path):
                        os.remove(self.cleanup_path)
                    if self.cleanup_dir and os.path.exists(self.cleanup_dir):
                        import shutil
                        shutil.rmtree(self.cleanup_dir, ignore_errors=True)
                except Exception as e:
                    print(f"Warning: Could not clean up export files: {e}")
    
    # Clean up progress tracking
    del export_progress[job_id]
    
    # Get the directory to clean up
    output_dir = os.path.dirname(output_path)
    
    return CleanupFileResponse(
        output_path,
        media_type="video/mp4",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
        cleanup_path=output_path,
        cleanup_dir=output_dir
    )


async def process_video_export_with_content(job_id: str, video_content: bytes, audio_content: bytes,
                                          video_filename: str, audio_filename: str,
                                          offset: float, crossfade: float, clip_video: bool):
    """Background task to process video export with progress tracking."""
    
    temp_dir = tempfile.mkdtemp()
    output_path = None
    
    try:
        # Update progress
        export_progress[job_id].update({
            "status": "uploading",
            "progress": 10,
            "message": "Saving uploaded files..."
        })
        
        # Save uploaded files
        video_path = os.path.join(temp_dir, f"input_video{os.path.splitext(video_filename)[1]}")
        audio_path = os.path.join(temp_dir, f"input_audio{os.path.splitext(audio_filename)[1]}")
        output_path = os.path.join(temp_dir, "output.mp4")
        progress_path = os.path.join(temp_dir, "progress.txt")
        
        # Write uploaded files to disk
        try:
            print(f"🔍 DEBUG: About to process files - video: {video_filename}, audio: {audio_filename}")
            print(f"🔍 DEBUG: Video content size: {len(video_content)} bytes")
            print(f"🔍 DEBUG: Audio content size: {len(audio_content)} bytes")
            
            print(f"🔍 DEBUG: Writing video to {video_path}")
            with open(video_path, "wb") as f:
                f.write(video_content)
            print("🔍 DEBUG: Video file written successfully")
            
            print(f"🔍 DEBUG: Writing audio to {audio_path}")
            with open(audio_path, "wb") as f:
                f.write(audio_content)
            print("🔍 DEBUG: Audio file written successfully")
                
        except Exception as e:
            print(f"❌ Error writing uploaded files: {e}")
            print(f"🔍 DEBUG: Exception type: {type(e)}")
            print(f"🔍 DEBUG: Exception args: {e.args}")
            import traceback
            print(f"🔍 DEBUG: Full traceback:\n{traceback.format_exc()}")
            export_progress[job_id].update({
                "status": "error",
                "error": f"Failed to save uploaded files: {str(e)}",
                "message": "File upload error"
            })
            return
        
        # Update progress
        export_progress[job_id].update({
            "status": "analyzing",
            "progress": 20,
            "message": "Analyzing video metadata..."
        })
        
        # Get video duration for progress calculation
        print(f"🔍 DEBUG: Getting video duration from {video_path}")
        duration = await get_video_duration(video_path)
        print(f"🔍 DEBUG: Video duration: {duration} seconds")
        
        # Build FFmpeg command with progress reporting
        print(f"🔍 DEBUG: Building FFmpeg command with params - offset: {offset}, crossfade: {crossfade}, clip_video: {clip_video}")
        cmd = await build_ffmpeg_command(video_path, audio_path, output_path, offset, crossfade, clip_video)
        cmd.extend(["-progress", progress_path])
        print(f"🔍 DEBUG: FFmpeg command built: {' '.join(cmd)}")
        
        # Verify input files exist
        print(f"🔍 DEBUG: Checking if input files exist:")
        print(f"🔍 DEBUG: Video file {video_path} exists: {os.path.exists(video_path)}")
        if os.path.exists(video_path):
            print(f"🔍 DEBUG: Video file size: {os.path.getsize(video_path)} bytes")
        print(f"🔍 DEBUG: Audio file {audio_path} exists: {os.path.exists(audio_path)}")
        if os.path.exists(audio_path):
            print(f"🔍 DEBUG: Audio file size: {os.path.getsize(audio_path)} bytes")
        
        # Update progress
        export_progress[job_id].update({
            "status": "processing",
            "progress": 30,
            "message": "Starting FFmpeg processing..."
        })
        
        # Start FFmpeg process
        print(f"🎬 Running FFmpeg: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(f"🔍 DEBUG: FFmpeg process started with PID: {process.pid}")
        
        # Monitor progress in separate thread
        progress_thread = threading.Thread(
            target=monitor_ffmpeg_progress,
            args=(job_id, progress_path, duration)
        )
        progress_thread.start()
        
        # Wait for FFmpeg to complete
        print("🔍 DEBUG: Waiting for FFmpeg to complete...")
        stdout, stderr = process.communicate(timeout=300)
        print(f"🔍 DEBUG: FFmpeg completed with return code: {process.returncode}")
        print(f"🔍 DEBUG: FFmpeg stdout: {stdout}")
        print(f"🔍 DEBUG: FFmpeg stderr: {stderr}")
        
        # Wait for progress thread to finish
        print("🔍 DEBUG: Waiting for progress thread to finish...")
        progress_thread.join(timeout=5)
        print("🔍 DEBUG: Progress thread finished")
        
        if process.returncode != 0:
            print(f"❌ FFmpeg failed with return code {process.returncode}")
            export_progress[job_id].update({
                "status": "error",
                "error": f"FFmpeg processing failed: {stderr}",
                "message": "Processing failed"
            })
            return
        
        print(f"🔍 DEBUG: Checking if output file exists: {output_path}")
        if not os.path.exists(output_path):
            print(f"❌ Output file not created at {output_path}")
            export_progress[job_id].update({
                "status": "error",
                "error": "Output file was not created",
                "message": "Export failed"
            })
            return
        
        output_size = os.path.getsize(output_path)
        print(f"🔍 DEBUG: Output file created successfully, size: {output_size} bytes")
        
        # Move output to persistent location before cleanup
        persistent_dir = tempfile.mkdtemp(prefix="export_")
        persistent_output = os.path.join(persistent_dir, f"synced_{video_filename}")
        print(f"🔍 DEBUG: Moving output from {output_path} to {persistent_output}")
        
        import shutil
        shutil.move(output_path, persistent_output)
        print(f"🔍 DEBUG: File moved successfully to persistent location")
        
        # Success!
        export_progress[job_id].update({
            "status": "complete",
            "progress": 100,
            "message": "Export complete! Ready for download.",
            "output_path": persistent_output
        })
        
    except subprocess.TimeoutExpired:
        export_progress[job_id].update({
            "status": "error",
            "error": "Processing timeout (5 minutes)",
            "message": "Export timed out"
        })
    except Exception as e:
        print(f"❌ Export error: {e}")
        export_progress[job_id].update({
            "status": "error",
            "error": f"Export failed: {str(e)}",
            "message": "Unexpected error"
        })
    finally:
        # Clean up temporary processing directory (but not the output file)
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"Warning: Could not clean up temp directory: {e}")


def monitor_ffmpeg_progress(job_id: str, progress_path: str, total_duration: float):
    """Monitor FFmpeg progress file and update progress."""
    
    while job_id in export_progress and export_progress[job_id]["status"] == "processing":
        try:
            if os.path.exists(progress_path):
                with open(progress_path, 'r') as f:
                    content = f.read()
                
                # Parse FFmpeg progress output
                current_time = 0
                for line in content.split('\n'):
                    if line.startswith('out_time_ms='):
                        current_time = int(line.split('=')[1]) / 1000000  # Convert microseconds to seconds
                        break
                
                if total_duration > 0:
                    progress_percent = min(95, 30 + (current_time / total_duration) * 65)  # 30-95% range
                    export_progress[job_id].update({
                        "progress": int(progress_percent),
                        "message": f"Processing... {current_time:.1f}s / {total_duration:.1f}s"
                    })
        
        except Exception as e:
            print(f"Progress monitoring error: {e}")
        
        time.sleep(2)  # Check every 2 seconds


async def get_video_duration(video_path: str) -> float:
    """Get video duration using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
    except Exception as e:
        print(f"Could not get video duration: {e}")
    
    return 0.0  # Fallback


async def build_ffmpeg_command(video_path: str, audio_path: str, output_path: str, 
                             offset: float, crossfade: float, clip_video: bool) -> list[str]:
    """Build FFmpeg command for video synchronization."""
    
    cmd = ["ffmpeg", "-y"]  # -y to overwrite output
    
    # Input files
    cmd.extend(["-i", video_path])
    cmd.extend(["-i", audio_path])
    
    # Build filter graph
    filters = []
    
    if clip_video:
        # Clip mode: trim video to match audio timing
        if offset > 0:
            # Positive offset: delay audio, trim video start
            filters.append(f"[0:v]trim=start={offset}[video_trimmed]")
            filters.append(f"[1:a]adelay={int(offset * 1000)}|{int(offset * 1000)}[audio_delayed]")
            video_input = "video_trimmed"
            audio_input = "audio_delayed"
        else:
            # Negative offset: advance audio, use original video
            filters.append(f"[1:a]atrim=start={abs(offset)}[audio_trimmed]")
            video_input = "0:v"
            audio_input = "audio_trimmed"
    else:
        # Silence mode: maintain full video duration
        if offset != 0:
            if offset > 0:
                # Positive offset: delay audio
                filters.append(f"[1:a]adelay={int(offset * 1000)}|{int(offset * 1000)}[audio_delayed]")
                audio_input = "audio_delayed"
            else:
                # Negative offset: pad with silence at start
                filters.append(f"[1:a]apad=pad_dur={abs(offset)}[audio_padded]")
                audio_input = "audio_padded"
        else:
            audio_input = "1:a"
        video_input = "0:v"
    
    # Handle crossfading if not 100% clean audio
    if crossfade < 100:
        # Extract original video audio
        original_level = (100 - crossfade) / 100
        clean_level = crossfade / 100
        
        if clip_video and offset > 0:
            # Trim original audio to match
            filters.append(f"[0:a]atrim=start={offset},volume={original_level}[orig_audio]")
        else:
            filters.append(f"[0:a]volume={original_level}[orig_audio]")
        
        filters.append(f"[{audio_input}]volume={clean_level}[clean_audio]")
        filters.append("[orig_audio][clean_audio]amix=inputs=2[final_audio]")
        final_audio = "final_audio"
    else:
        final_audio = audio_input
    
    # Apply filters if any
    if filters:
        filter_complex = ";".join(filters)
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", f"[{video_input}]", "-map", f"[{final_audio}]"])
    else:
        cmd.extend(["-map", "0:v", "-map", "1:a"])
    
    # Fast encoding - copy video stream when possible
    if clip_video and offset > 0:
        # If we're trimming video, we need to re-encode
        cmd.extend([
            "-c:v", "libx264",           # H.264 video codec
            "-preset", "ultrafast",      # Fastest encoding
            "-crf", "23",               # Reasonable quality
            "-pix_fmt", "yuv420p",      # Compatible pixel format
        ])
    else:
        # Copy video stream without re-encoding (much faster)
        cmd.extend(["-c:v", "copy"])
    
    # Audio encoding settings
    cmd.extend([
        "-c:a", "aac",              # AAC audio codec
        "-b:a", "128k",             # Audio bitrate
        "-ar", "48000",             # Sample rate
        "-ac", "2",                 # Stereo audio
        "-movflags", "+faststart",  # Web-optimized
        "-f", "mp4",                # Force MP4 format
        output_path
    ])
    
    return cmd


def render_video_sync_content():
    """Render the video sync page content."""
    with tag.div("w-full h-screen bg-neutral-900 text-white flex flex-col"):
        # Compact upload header (only visible when files not loaded)
        with tag.div("bg-neutral-800 border-b border-neutral-700", id="upload-header"):
            render_file_upload_section()
        
        # Main layout: optimized horizontal split
        with tag.div("flex-1 flex bg-neutral-900", id="main-layout", style="display: none;"):
            # Video section - larger
            with tag.div("flex-1 flex items-center justify-center bg-black border-r border-neutral-600"):
                render_video_player_section()
            
            # Inspector panel - wider for better waveforms
            with tag.div("w-96 bg-neutral-900 flex flex-col"):
                render_inspector_panel()


def render_file_upload_section():
    """Render the compact file upload area."""
    with tag.div("p-4"):
        with tag.form("flex gap-4 items-center", enctype="multipart/form-data"):
            # App title
            with tag.div("flex items-center gap-2"):
                with tag.div("text-xl font-bold text-white"):
                    text("🎬 Video Sync")
            
            # Video upload - compact
            with tag.div("flex items-center gap-3 bg-neutral-700 rounded-lg p-3"):
                with tag.input(
                    "hidden",
                    type="file",
                    id="video-upload",
                    accept="video/*"
                ):
                    pass
                with tag.label(
                    "px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded cursor-pointer transition-colors",
                    **{"for": "video-upload"}
                ):
                    text("📹 Video")
                with tag.div("text-xs text-neutral-300 min-w-0", id="video-status"):
                    text("No video")
            
            # Audio upload - compact
            with tag.div("flex items-center gap-3 bg-neutral-700 rounded-lg p-3"):
                with tag.input(
                    "hidden",
                    type="file",
                    id="audio-upload",
                    accept="audio/*,.mpeg,.mp3,.wav,.m4a"
                ):
                    pass
                with tag.label(
                    "px-3 py-1 bg-green-600 hover:bg-green-700 text-white text-sm rounded cursor-pointer transition-colors",
                    **{"for": "audio-upload"}
                ):
                    text("🎵 Audio")
                with tag.div("text-xs text-neutral-300 min-w-0", id="audio-status"):
                    text("No audio")


def render_video_player_section():
    """Render the video player optimized for space."""
    with tag.div("p-6"):
        with tag.video(
            "max-w-full max-h-full object-contain shadow-lg",
            id="video-player",
            controls=True,
            preload="metadata",
            style="max-height: 85vh;"
        ):
            text("Your browser does not support the video tag.")
    
    # Hidden audio players
    with tag.audio("hidden", id="original-audio-player", preload="metadata"):
        text("Your browser does not support the audio tag.")
    with tag.audio("hidden", id="clean-audio-player", preload="metadata"):
        text("Your browser does not support the audio tag.")


def render_inspector_panel():
    """Render optimized inspector panel with better waveforms."""
    with tag.div("flex flex-col h-full"):
        # Header
        with tag.div("px-4 py-3 bg-neutral-800 border-b border-neutral-600"):
            with tag.div("text-sm font-semibold text-white"):
                text("🎬 Audio Sync")
        
        # Large waveforms section - takes most space
        with tag.div("p-4 border-b border-neutral-700 flex-1"):
            with tag.div("space-y-4"):
                # Video audio waveform
                with tag.div():
                    with tag.div("flex items-center justify-between mb-2"):
                        with tag.div("text-sm font-medium text-neutral-300"):
                            text("Video Audio")
                        with tag.div("text-xs text-red-400 font-mono"):
                            text("Original")
                    with tag.div("relative"):
                        with tag.canvas(
                            "w-full h-20 border border-neutral-600 rounded bg-neutral-800",
                            id="original-waveform",
                            width="320",
                            height="80"
                        ):
                            pass
                
                # Clean audio waveform  
                with tag.div():
                    with tag.div("flex items-center justify-between mb-2"):
                        with tag.div("text-sm font-medium text-neutral-300"):
                            text("Clean Audio")
                        with tag.div("text-xs text-blue-400 font-mono"):
                            text("Replacement")
                    with tag.div("relative"):
                        with tag.canvas(
                            "w-full h-20 border border-neutral-600 rounded bg-neutral-800",
                            id="clean-waveform", 
                            width="320",
                            height="80"
                        ):
                            pass
                        
                        # Playhead indicator spans both waveforms
                        with tag.div(
                            "absolute w-0.5 bg-yellow-400 opacity-90 pointer-events-none z-10",
                            id="playhead",
                            style="top: -88px; height: 168px; left: 0px; transition: left 0.1s ease-out;"
                        ):
                            pass
                
                # Audio mix slider
                with tag.div("mt-4"):
                    with tag.div("flex justify-between items-center mb-2"):
                        with tag.span("text-xs text-red-400"):
                            text("Original")
                        with tag.span("text-xs text-neutral-400"):
                            text("Audio Mix")
                        with tag.span("text-xs text-blue-400"):
                            text("Clean")
                    with tag.input(
                        "w-full h-3 bg-neutral-700 rounded-lg appearance-none cursor-pointer",
                        type="range",
                        id="crossfader",
                        min="0",
                        max="100",
                        value="50",
                        style="background: linear-gradient(to right, #ef4444 0%, #ef4444 50%, #3b82f6 50%, #3b82f6 100%)"
                    ):
                        pass
                
                # Clip video option
                with tag.div("mt-3 flex items-center gap-2"):
                    with tag.input(
                        "w-4 h-4 text-blue-600 bg-neutral-700 border-neutral-600 rounded focus:ring-blue-500 focus:ring-2",
                        type="checkbox",
                        id="clip-video-checkbox"
                    ):
                        pass
                    with tag.label("text-xs text-neutral-300", **{"for": "clip-video-checkbox"}):
                        text("Clip video instead of adding silence")
                    with tag.div(
                        "ml-auto text-xs text-neutral-500 cursor-help",
                        title="When checked: trims video length to match audio timing. When unchecked: adds silence to maintain full video duration."
                    ):
                        text("?")
        
        # Compact controls section
        with tag.div("p-4 space-y-3 bg-neutral-850"):
            # Sync controls - horizontal layout
            with tag.div():
                with tag.div("flex items-center justify-between mb-2"):
                    with tag.label("text-sm font-medium text-white"):
                        text("Sync Offset")
                    with tag.div("text-sm text-blue-400 font-mono", id="sync-status"):
                        text("0.00s")
                
                # Offset input and fine tune in one row
                with tag.div("flex items-center gap-2 mb-2"):
                    with tag.input(
                        "w-20 px-2 py-1 bg-neutral-700 border border-neutral-600 rounded text-white text-sm",
                        type="number",
                        id="audio-offset",
                        step="0.01",
                        value="0"
                    ):
                        pass
                    with tag.span("text-xs text-neutral-400 mr-2"):
                        text("sec")
                    
                    # Fine tune buttons
                    with tag.button(
                        "px-2 py-1 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded transition-colors",
                        onclick="adjustOffset(-0.1)"
                    ):
                        text("-0.1")
                    with tag.button(
                        "px-2 py-1 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded transition-colors",
                        onclick="adjustOffset(-0.01)"
                    ):
                        text("-0.01")
                    with tag.button(
                        "px-2 py-1 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded transition-colors",
                        onclick="adjustOffset(0.01)"
                    ):
                        text("+0.01")
                    with tag.button(
                        "px-2 py-1 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded transition-colors",
                        onclick="adjustOffset(0.1)"
                    ):
                        text("+0.1")
                
                # Visual offset indicator
                with tag.div("h-1 bg-neutral-700 rounded relative"):
                    with tag.div(
                        "absolute h-1 w-1 bg-blue-400 rounded-full transform -translate-x-1/2",
                        id="offset-indicator",
                        style="left: 50%; transition: left 0.2s ease-out;"
                    ):
                        pass
            
            # Playback controls - compact horizontal
            with tag.div():
                with tag.div("flex items-center gap-2 mb-2"):
                    with tag.button(
                        "flex-1 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded font-medium transition-colors",
                        id="play-pause-btn",
                        onclick="togglePlayback()"
                    ):
                        text("▶ Play")
                    with tag.button(
                        "px-3 py-2 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded transition-colors",
                        onclick="seekToPosition(0)"
                    ):
                        text("⏮ Reset")
                    with tag.button(
                        "px-3 py-2 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded transition-colors",
                        onclick="autoDetectSync()"
                    ):
                        text("🎯 Auto")
                
                # Speed controls - one row
                with tag.div("flex gap-1"):
                    with tag.button(
                        "flex-1 px-2 py-1 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded transition-colors",
                        onclick="setPlaybackRate(0.25)"
                    ):
                        text("0.25x")
                    with tag.button(
                        "flex-1 px-2 py-1 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded transition-colors",
                        onclick="setPlaybackRate(0.5)"
                    ):
                        text("0.5x")
                    with tag.button(
                        "flex-1 px-2 py-1 bg-blue-700 hover:bg-blue-800 text-white text-xs rounded transition-colors",
                        onclick="setPlaybackRate(1.0)"
                    ):
                        text("1.0x")
        
        # Export buttons
        with tag.div("p-4 bg-neutral-800 border-t border-neutral-600"):
            with tag.div("space-y-2"):
                with tag.button(
                    "w-full px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm rounded font-medium transition-colors",
                    id="export-btn",
                    onclick="exportVideo()"
                ):
                    text("📹 Export (Browser)")
                
                with tag.button(
                    "w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded font-medium transition-colors",
                    id="export-server-btn",
                    onclick="exportVideoServer()"
                ):
                    text("🖥️ Export (Server)")
            
            with tag.div("text-xs text-neutral-400 text-center mt-2", id="export-status"):
                text("Ready when synced perfectly")
        
        # Add mp4box.js for proper MP4 muxing
        with tag.script(src="https://cdn.jsdelivr.net/npm/mp4box@0.5.4/dist/mp4box.all.min.js"):
            pass
        
        # Add external JavaScript for audio processing and waveforms
        with tag.script(src="/static/video-sync.js"):
            pass
