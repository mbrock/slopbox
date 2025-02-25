import os
from typing import Optional
from urllib.parse import urlencode

from tagflow import attr, html, tag, text

from slopbox.fastapi import app
from slopbox.model import Image


@html.div(
    "h-screen w-screen",
    "flex flex-col",
    "items-center justify-center",
    "relative",
    "bg-stone-900",
    id="slideshow-container",
)
def render_slideshow(
    image: Optional[Image],
    image_count: Optional[int] = None,
    spec_id: Optional[int] = None,
    liked_only: bool = False,
):
    """Render the slideshow view with a single image and auto-refresh."""
    render_slideshow_content(image, image_count, spec_id, liked_only)


@html.div(
    "flex flex-col",
    "items-center justify-center",
    "relative",
    id="slideshow-content",
    hx_target="#slideshow-content",
    hx_swap="outerHTML",
    hx_trigger="every 1s",
)
def render_slideshow_content(
    image: Optional[Image],
    image_count: Optional[int] = None,
    spec_id: Optional[int] = None,
    liked_only: bool = False,
):
    """Render just the content of the slideshow that needs to be updated."""

    if liked_only:
        next_url = app.url_path_for("slideshow_liked_next")
    else:
        next_url = app.url_path_for("slideshow_next")
        params = {}
        if spec_id is not None:
            params["spec_id"] = spec_id
        if params:
            next_url += "?" + urlencode(params)

    attr("hx-get", next_url)

    if image and image.status == "complete" and image.filepath:
        assert image.spec is not None
        with tag.div(
            "bg-white rounded-lg shadow-2xl shadow-neutral-700",
            id="image-container",
        ):
            # Image with padding
            with tag.img(
                "object-contain max-h-screen max-w-screen",
                src=f"/images/{os.path.basename(image.filepath)}",
                alt=image.spec.prompt,
            ):
                pass
    else:
        with tag.div("text-white text-2xl"):
            text("No images available")
