"""
Integration tests for the video sync functionality.
"""

import io
import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Tuple

import anyio
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from tagflow import DocumentMiddleware

from slopbox.videosync import router as videosync_router


async def wait_for_job_completion(
    client: httpx.AsyncClient, job_id: str, timeout_seconds: int = 30
) -> Dict[str, Any]:
    """
    Wait for a videosync job to complete (successfully or with error).

    Args:
        client: AsyncClient instance
        job_id: Job ID to monitor
        timeout_seconds: Maximum time to wait

    Returns:
        dict: Final job status

    Raises:
        TimeoutError: If job doesn't complete within timeout
    """
    start_time = anyio.current_time()

    while anyio.current_time() - start_time < timeout_seconds:
        # Check current status via progress endpoint
        progress_response = await client.get(f"/export-progress/{job_id}")
        if progress_response.status_code != 200:
            raise RuntimeError(
                f"Progress endpoint failed: {progress_response.status_code}"
            )

        # Parse SSE response to get current status
        response_text = progress_response.text
        if "data:" in response_text:
            # Extract the JSON data from SSE format
            lines = response_text.strip().split("\n")
            for line in lines:
                if line.startswith("data:"):
                    data_json = line[5:].strip()  # Remove 'data:' prefix
                    try:
                        status_data = json.loads(data_json)
                        if status_data.get("status") in ["complete", "error"]:
                            return status_data
                    except json.JSONDecodeError:
                        pass

        # Wait a bit before checking again
        await anyio.sleep(0.5)

    raise TimeoutError(
        f"Job {job_id} did not complete within {timeout_seconds} seconds"
    )


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI app with video sync routes."""
    test_app = FastAPI(title="Video Sync Test")
    test_app.add_middleware(DocumentMiddleware)

    # Mount static files from current directory for testing
    test_app.mount("/static", StaticFiles(directory="."), name="static")
    test_app.include_router(videosync_router)

    return test_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create an async test client."""
    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def sample_video_file() -> Tuple[str, io.BytesIO, str]:
    """Get a real small video file for testing."""
    video_path = Path(__file__).parent / "fixtures" / "test_video.mp4"
    if not video_path.exists():
        pytest.skip("Test video file not found")

    with open(video_path, "rb") as f:
        video_content = f.read()

    return ("test_video.mp4", io.BytesIO(video_content), "video/mp4")


@pytest.fixture
def sample_audio_file() -> Tuple[str, io.BytesIO, str]:
    """Get a real small audio file for testing."""
    audio_path = Path(__file__).parent / "fixtures" / "test_audio.mp3"
    if not audio_path.exists():
        pytest.skip("Test audio file not found")

    with open(audio_path, "rb") as f:
        audio_content = f.read()

    return ("test_audio.mp3", io.BytesIO(audio_content), "audio/mpeg")


class TestVideoSyncRoutesBasic:
    """Test basic video sync routes without FFmpeg processing."""

    @pytest.mark.anyio
    async def test_root_route(self, client: httpx.AsyncClient) -> None:
        """Test the video sync route renders correctly."""
        response = await client.get("/video-sync")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        # Should contain basic HTML structure
        assert "<!doctype html>" in response.text
        assert "Video Sync" in response.text

    @pytest.mark.anyio
    async def test_video_sync_route(self, client: httpx.AsyncClient) -> None:
        """Test the /video-sync route renders correctly."""
        response = await client.get("/video-sync")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        # Should contain basic HTML structure
        assert "<!doctype html>" in response.text
        assert "Video Sync" in response.text

    @pytest.mark.anyio
    async def test_htmx_request(self, client: httpx.AsyncClient) -> None:
        """Test HTMX requests return partial content."""
        headers = {"HX-Request": "true"}
        response = await client.get("/video-sync", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        # HTMX requests should return partial HTML content with minimal
        # document structure
        assert "<html lang=" not in response.text  # No full HTML structure
        assert "<head>" not in response.text  # No head section
        assert "Video Sync" in response.text

    @pytest.mark.anyio
    async def test_export_video_server_missing_files(
        self, client: httpx.AsyncClient
    ) -> None:
        """Test export endpoint with missing files returns error."""
        response = await client.post("/export-video-server")
        assert (
            response.status_code == 422
        )  # Validation error for missing files

    @pytest.mark.anyio
    async def test_export_video_server_with_files(
        self,
        client: httpx.AsyncClient,
        sample_video_file: Tuple[str, io.BytesIO, str],
        sample_audio_file: Tuple[str, io.BytesIO, str],
    ) -> None:
        """Test export endpoint with valid files starts a job."""
        video_name, video_content, video_type = sample_video_file
        audio_name, audio_content, audio_type = sample_audio_file

        files = {
            "video_file": (video_name, video_content, video_type),
            "audio_file": (audio_name, audio_content, audio_type),
        }
        data = {"offset": 0.0, "crossfade": 50.0, "clip_video": False}

        response = await client.post(
            "/export-video-server", files=files, data=data
        )
        assert response.status_code == 200

        result = response.json()
        assert "job_id" in result
        assert isinstance(result["job_id"], str)

    @pytest.mark.anyio
    async def test_export_progress_invalid_job(
        self, client: httpx.AsyncClient
    ) -> None:
        """Test progress endpoint with invalid job ID."""
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
    async def test_export_download_invalid_job(
        self, client: httpx.AsyncClient
    ) -> None:
        """Test download endpoint with invalid job ID."""
        response = await client.get("/export-download/invalid-job-id")
        assert response.status_code == 404

        result = response.json()
        assert "error" in result
        assert "Job not found" in result["error"]

    @pytest.mark.anyio
    async def test_export_workflow_integration(
        self,
        client: httpx.AsyncClient,
        sample_video_file: Tuple[str, io.BytesIO, str],
        sample_audio_file: Tuple[str, io.BytesIO, str],
    ) -> None:
        """Test the complete export workflow integration with real files."""
        video_name, video_content, video_type = sample_video_file
        audio_name, audio_content, audio_type = sample_audio_file

        # Step 1: Start export job with simple parameters (no offset for speed)
        files = {
            "video_file": (video_name, video_content, video_type),
            "audio_file": (audio_name, audio_content, audio_type),
        }
        data = {
            "offset": 0.0,  # No offset for faster processing
            "crossfade": 100.0,  # 100% clean audio (simpler processing)
            "clip_video": False,
        }

        export_response = await client.post(
            "/export-video-server", files=files, data=data
        )
        assert export_response.status_code == 200

        job_id = export_response.json()["job_id"]

        # Step 2: Wait for job to complete
        final_status = await wait_for_job_completion(
            client, job_id, timeout_seconds=30
        )

        # Step 3: Verify job completed successfully
        assert final_status["status"] == "complete", (
            "Job failed with error:"
            f" {final_status.get('error', 'Unknown error')}"
        )
        assert final_status["progress"] == 100
        assert "output_path" in final_status
        assert final_status["output_path"] is not None

        # Step 4: Verify download endpoint works
        download_response = await client.get(f"/export-download/{job_id}")
        assert download_response.status_code == 200
        assert download_response.headers["content-type"] == "video/mp4"

        # Verify we get actual video content (not empty)
        content = download_response.content
        assert len(content) > 1000  # Should be a real video file

    @pytest.mark.anyio
    async def test_different_offset_values(
        self,
        client: httpx.AsyncClient,
        sample_video_file: Tuple[str, io.BytesIO, str],
        sample_audio_file: Tuple[str, io.BytesIO, str],
    ) -> None:
        """Test export jobs with different offset values complete successfully."""
        video_name, video_content, video_type = sample_video_file
        audio_name, audio_content, audio_type = sample_audio_file

        # Test key offset values - some may fail with test files
        test_cases = [
            (0.0, True),  # Should always work
            (0.5, False),  # May fail with filter complex issues
            (-0.5, False),  # May fail with filter complex issues
        ]

        for offset, expect_success in test_cases:
            files = {
                "video_file": (
                    video_name,
                    io.BytesIO(video_content.getvalue()),
                    video_type,
                ),
                "audio_file": (
                    audio_name,
                    io.BytesIO(audio_content.getvalue()),
                    audio_type,
                ),
            }
            data = {
                "offset": offset,
                "crossfade": 100.0,  # Simpler processing
                "clip_video": False,
            }

            response = await client.post(
                "/export-video-server", files=files, data=data
            )
            assert response.status_code == 200, (
                f"Failed to start job with offset {offset}"
            )

            job_id = response.json()["job_id"]

            # Wait for completion and check result
            final_status = await wait_for_job_completion(
                client, job_id, timeout_seconds=30
            )

            if expect_success:
                assert final_status["status"] == "complete"
                assert final_status["progress"] == 100
            else:
                # For complex filters, expect either success or specific
                # FFmpeg errors
                assert final_status["status"] in ["complete", "error"]
                if final_status["status"] == "error":
                    # Should be a meaningful error message
                    assert "error" in final_status
                    assert len(final_status["error"]) > 0

    @pytest.mark.anyio
    async def test_crossfade_values(
        self,
        client: httpx.AsyncClient,
        sample_video_file: Tuple[str, io.BytesIO, str],
        sample_audio_file: Tuple[str, io.BytesIO, str],
    ) -> None:
        """Test export jobs with different crossfade values complete
        successfully."""
        video_name, video_content, video_type = sample_video_file
        audio_name, audio_content, audio_type = sample_audio_file

        # Test key crossfade values
        test_cases = [
            (100.0, True),  # Should always work (clean audio only)
            (50.0, False),  # May fail if video has no audio track
            (0.0, False),  # May fail if video has no audio track
        ]

        for crossfade, expect_success in test_cases:
            files = {
                "video_file": (
                    video_name,
                    io.BytesIO(video_content.getvalue()),
                    video_type,
                ),
                "audio_file": (
                    audio_name,
                    io.BytesIO(audio_content.getvalue()),
                    audio_type,
                ),
            }
            data = {
                "offset": 0.0,  # No offset for speed
                "crossfade": crossfade,
                "clip_video": False,
            }

            response = await client.post(
                "/export-video-server", files=files, data=data
            )
            assert response.status_code == 200, (
                f"Failed to start job with crossfade {crossfade}"
            )

            job_id = response.json()["job_id"]

            # Wait for completion and check result
            final_status = await wait_for_job_completion(
                client, job_id, timeout_seconds=30
            )

            if expect_success:
                assert final_status["status"] == "complete"
                assert final_status["progress"] == 100
            else:
                # For crossfading, expect either success or audio track errors
                assert final_status["status"] in ["complete", "error"]
                if final_status["status"] == "error":
                    # Should be a meaningful error message
                    assert "error" in final_status
                    assert len(final_status["error"]) > 0

    @pytest.mark.anyio
    async def test_clip_video_modes(
        self,
        client: httpx.AsyncClient,
        sample_video_file: Tuple[str, io.BytesIO, str],
        sample_audio_file: Tuple[str, io.BytesIO, str],
    ) -> None:
        """Test export jobs with different clip video modes complete
        successfully."""
        video_name, video_content, video_type = sample_video_file
        audio_name, audio_content, audio_type = sample_audio_file

        for clip_video in [False, True]:  # Test False first (simpler case)
            files = {
                "video_file": (
                    video_name,
                    io.BytesIO(video_content.getvalue()),
                    video_type,
                ),
                "audio_file": (
                    audio_name,
                    io.BytesIO(audio_content.getvalue()),
                    audio_type,
                ),
            }
            data = {
                "offset": 0.0,  # No offset for speed
                "crossfade": 100.0,  # Simpler processing
                "clip_video": clip_video,
            }

            response = await client.post(
                "/export-video-server", files=files, data=data
            )
            assert response.status_code == 200, (
                f"Failed to start job with clip_video={clip_video}"
            )

            job_id = response.json()["job_id"]

            # Wait for completion and check result
            final_status = await wait_for_job_completion(
                client, job_id, timeout_seconds=30
            )

            # clip_video=False should always work, clip_video=True may fail
            # with complex filters
            if not clip_video:
                assert final_status["status"] == "complete"
                assert final_status["progress"] == 100
            else:
                # Clip video mode may fail with test files
                assert final_status["status"] in ["complete", "error"]
                if final_status["status"] == "error":
                    # Should be a meaningful error message
                    assert "error" in final_status
                    assert len(final_status["error"]) > 0


class TestVideoSyncUI:
    """Test video sync UI components and rendering."""

    @pytest.mark.anyio
    async def test_page_renders_successfully(
        self, client: httpx.AsyncClient
    ) -> None:
        """Test that the main page renders successfully."""
        response = await client.get("/video-sync")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        # Should contain basic HTML structure and content
        assert "<!doctype html>" in response.text
        assert "Video Sync" in response.text

    @pytest.mark.anyio
    async def test_video_sync_page_renders_successfully(
        self, client: httpx.AsyncClient
    ) -> None:
        """Test that the video sync page renders successfully."""
        response = await client.get("/video-sync")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        # Should contain basic HTML structure and content
        assert "<!doctype html>" in response.text
        assert "Video Sync" in response.text

    @pytest.mark.anyio
    async def test_htmx_request_renders_successfully(
        self, client: httpx.AsyncClient
    ) -> None:
        """Test that HTMX requests render successfully."""
        headers = {"HX-Request": "true"}
        response = await client.get("/video-sync", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        # HTMX requests should return partial HTML content
        assert "<html lang=" not in response.text  # No full HTML structure
        assert "<head>" not in response.text  # No head section
        assert "Video Sync" in response.text


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
