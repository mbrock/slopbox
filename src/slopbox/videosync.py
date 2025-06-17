import asyncio
import json
import os
import subprocess
import tempfile
import threading
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Form, Request, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from tagflow import tag, text

from slopbox.ui import render_base_layout

# Create the router for video sync functionality
router = APIRouter()

# Global progress tracking
export_progress = {}


@router.get("/")
async def video_sync_root(request: Request):
    """Serve the video-audio synchronization page at root."""
    if request.headers.get("HX-Request"):
        render_video_sync_content()
    else:
        with render_base_layout():
            render_video_sync_content()


@router.get("/video-sync")
async def video_sync(request: Request):
    """Serve the video-audio synchronization page."""
    if request.headers.get("HX-Request"):
        render_video_sync_content()
    else:
        with render_base_layout():
            render_video_sync_content()


@router.post("/export-video-server")
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


@router.get("/export-progress/{job_id}")
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


@router.get("/export-download/{job_id}")
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
            
            # Playback controls  
            with tag.div():
                with tag.div("text-sm font-medium text-white mb-2"):
                    text("Playback")
                
                with tag.div("flex gap-2 mb-2"):
                    with tag.button(
                        "flex-1 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded font-medium transition-colors",
                        id="play-pause-btn",
                        onclick="togglePlayback()"
                    ):
                        text("▶ Play")
                    
                    with tag.button(
                        "px-3 py-2 bg-neutral-700 hover:bg-neutral-600 text-white text-sm rounded transition-colors",
                        onclick="resetPlayback()"
                    ):
                        text("⏹ Reset")
                    
                    with tag.div("flex items-center gap-1"):
                        with tag.label("text-xs text-neutral-400", **{"for": "auto-checkbox"}):
                            text("Auto")
                        with tag.input(
                            "w-4 h-4 text-blue-600 bg-neutral-700 border-neutral-600 rounded focus:ring-blue-500 focus:ring-2",
                            type="checkbox",
                            id="auto-checkbox",
                            checked=True
                        ):
                            pass
                
                # Speed controls
                with tag.div("flex gap-1"):
                    with tag.button(
                        "px-2 py-1 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded transition-colors",
                        onclick="setPlaybackRate(0.25)"
                    ):
                        text("0.25x")
                    with tag.button(
                        "px-2 py-1 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded transition-colors",
                        onclick="setPlaybackRate(0.5)"
                    ):
                        text("0.5x")
                    with tag.button(
                        "px-2 py-1 bg-blue-600 text-white text-xs rounded",
                        onclick="setPlaybackRate(1.0)"
                    ):
                        text("1.0x")
            
            # Export section
            with tag.div():
                with tag.div("text-sm font-medium text-white mb-2"):
                    text("Export")
                
                with tag.div("text-xs text-green-400 mb-2", id="export-status"):
                    text("Ready when synced.")
                
                with tag.div("flex gap-2"):
                    with tag.button(
                        "flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 text-white text-sm rounded font-medium transition-colors",
                        id="export-browser-btn",
                        onclick="exportVideo()"
                    ):
                        text("🌐 Export (Browser)")
                    
                    with tag.button(
                        "flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 text-white text-sm rounded font-medium transition-colors",
                        id="export-server-btn",
                        onclick="exportVideoServer()"
                    ):
                        text("🖥️ Export (Server)")
                
                # Progress bar (hidden by default)
                with tag.div("mt-2 hidden", id="export-progress-container"):
                    with tag.div("w-full bg-neutral-700 rounded-full h-2"):
                        with tag.div(
                            "bg-green-600 h-2 rounded-full transition-all duration-300",
                            id="export-progress-bar",
                            style="width: 0%"
                        ):
                            pass
                    with tag.div("text-xs text-neutral-400 mt-1", id="export-progress-text"):
                        text("Starting export...")
        
        # JavaScript
        with tag.script(src="/static/video-sync.js"):
            pass