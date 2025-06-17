#!/usr/bin/env python3
"""
Command line entry points for slopbox.
"""

import sys
import click


@click.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=8000, type=int, help="Port to bind to")
@click.option("--no-reload", is_flag=True, help="Disable auto-reload")
def slopbox_cli(host, port, no_reload):
    """Slopbox - AI image generation platform with gallery and prompt management."""
    click.echo("🎨 Starting Slopbox")
    click.echo("   AI image generation platform with gallery and prompt management")
    click.echo("   Includes video sync tool at /video-sync")
    click.echo(f"   Server will be available at: http://{host}:{port}")
    click.echo()
    
    try:
        import uvicorn
        uvicorn.run("slopbox.app:app", host=host, port=port, reload=not no_reload)
    except KeyboardInterrupt:
        click.echo("\n👋 Slopbox stopped")
        sys.exit(0)


@click.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=8000, type=int, help="Port to bind to")
@click.option("--no-reload", is_flag=True, help="Disable auto-reload")
def videosync_cli(host, port, no_reload):
    """Video Sync Tool - Browser-based video-audio synchronization with waveform visualization."""
    click.echo("🎬 Starting Video Sync Tool")
    click.echo("   Browser-based video-audio synchronization with waveform visualization")
    click.echo("   Upload video and audio files to sync them with real-time preview")
    click.echo(f"   Server will be available at: http://{host}:{port}")
    click.echo()
    
    try:
        # Create the standalone videosync app
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from tagflow import DocumentMiddleware
        from slopbox.videosync import router
        
        app = FastAPI(
            title="Video Sync Tool",
            description="Browser-based video-audio synchronization with real-time waveform visualization"
        )
        app.add_middleware(DocumentMiddleware)
        app.mount("/static", StaticFiles(directory="static"), name="static")
        app.include_router(router)
        
        import uvicorn
        uvicorn.run(app, host=host, port=port, reload=not no_reload)
    except KeyboardInterrupt:
        click.echo("\n👋 Video sync stopped")
        sys.exit(0)