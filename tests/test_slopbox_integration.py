"""
Integration tests for slopbox main app with videosync router.
"""

import httpx
import pytest
from httpx import ASGITransport

from slopbox.app import app


@pytest.fixture
async def client():
    """Create an async test client for the main slopbox app."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        yield ac


class TestSlopboxVideoSyncIntegration:
    """Test that videosync router is properly mounted in main slopbox app."""

    @pytest.mark.anyio
    async def test_videosync_root_mounted(self, client):
        """Test that videosync root route is accessible through main app."""
        response = await client.get("/")
        assert response.status_code == 200
        # Should redirect to gallery, but route should exist

    @pytest.mark.anyio
    async def test_videosync_page_mounted(self, client):
        """Test that /video-sync route is accessible through main app."""
        response = await client.get("/video-sync")
        assert response.status_code == 200
        # TagFlow returns JSON null in test context, but route should work

    @pytest.mark.anyio
    async def test_videosync_export_endpoint_mounted(self, client):
        """Test that videosync export endpoint is accessible through main
        app."""
        # Test with no files - should get validation error
        response = await client.post("/export-video-server")
        assert (
            response.status_code == 422
        )  # Validation error for missing files

    @pytest.mark.anyio
    async def test_videosync_progress_endpoint_mounted(self, client):
        """Test that videosync progress endpoint is accessible through main
        app."""
        response = await client.get("/export-progress/invalid-job-id")
        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "text/event-stream; charset=utf-8"
        )
        # Should return error in SSE format
        assert "data:" in response.text
        assert "error" in response.text

    @pytest.mark.anyio
    async def test_videosync_download_endpoint_mounted(self, client):
        """Test that videosync download endpoint is accessible through main app."""
        response = await client.get("/export-download/invalid-job-id")
        assert response.status_code == 404
        result = response.json()
        assert "error" in result
        assert "Job not found" in result["error"]

    @pytest.mark.anyio
    async def test_main_gallery_still_works(self, client):
        """Test that main app gallery functionality still works after videosync mount."""
        response = await client.get("/gallery")
        assert response.status_code == 200
        # Should work - this is the main slopbox functionality

    @pytest.mark.anyio
    async def test_static_files_mounted(self, client):
        """Test that static files are properly mounted and accessible."""
        # Test that video-sync.js is accessible (needed for videosync functionality)
        response = await client.get("/static/video-sync.js")
        assert response.status_code == 200
        # Should be JavaScript content
        assert "AudioSyncApp" in response.text
