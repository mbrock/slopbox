#!/usr/bin/env python3
"""
Standalone Video Sync Application

A lightweight FastAPI app that serves only the video-audio synchronization tool.
Can be run independently from the main slopbox application.

Usage:
    python videosync_app.py [--port 8000] [--host 0.0.0.0]
"""

import argparse
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from tagflow import DocumentMiddleware

from slopbox.videosync import router as videosync_router
from slopbox.ui import render_base_layout

# Create the standalone FastAPI app
app = FastAPI(
    title="Video Sync Tool",
    description="Browser-based video-audio synchronization with real-time waveform visualization",
    version="1.0.0"
)

# Add tagflow middleware for HTML rendering
app.add_middleware(DocumentMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include the video sync router
app.include_router(videosync_router)


def main():
    """Main entry point for the standalone video sync app."""
    parser = argparse.ArgumentParser(description="Video Sync Tool - Standalone Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()
    
    print(f"🎬 Starting Video Sync Tool on http://{args.host}:{args.port}")
    print("   Upload video and audio files to synchronize them with real-time waveform visualization")
    print("   Supports both browser-based and server-side FFmpeg export")
    
    uvicorn.run(
        "videosync_app:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()