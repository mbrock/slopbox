from typing import List, Tuple
from urllib.parse import urlencode

from tagflow import attr, html, tag, text

from slopbox.fastapi import app
from slopbox.image.spec import render_spec_block
from slopbox.model import Image, ImageSpec
from slopbox.prompt.form import render_prompt_form_dropdown
from slopbox.ui import Styles


@html.div("h-full overflow-y-auto flex-1 flex flex-col items-stretch")
def render_image_gallery(
    specs_with_images: List[Tuple[ImageSpec, List[Image]]],
    current_page: int,
    total_pages: int,
    sort_by: str = "recency",
    liked_only: bool = False,
):
    """Render the image gallery with navigation bar and content."""
    # Render top navigation bar containing prompt form and gallery controls
    with tag.div(
        "sticky top-0 z-50",
        "bg-neutral-200 shadow-md",
        "flex items-center justify-between",
        "px-4 py-2 gap-4",
    ):
        with tag.div("flex items-center gap-4"):
            render_sort_options(sort_by, liked_only)
            render_slideshow_link()
            render_delete_unliked_button()

        render_prompt_form_dropdown()

    with tag.div("p-2", id="gallery-container"):
        for spec, images in specs_with_images:
            render_spec_block(spec, images, liked_only)

    # Pagination controls at the bottom
    render_pagination_controls(current_page, total_pages, sort_by, liked_only)


def make_gallery_url(page: int, sort_by: str, liked_only: bool) -> str:
    """Generate a URL for the gallery with the given parameters."""
    params = {
        "page": page,
        "sort_by": sort_by,
    }
    if liked_only:
        params["liked_only"] = "true"
    return app.url_path_for("gallery") + "?" + urlencode(params)


def render_pagination_controls(
    current_page, total_pages, sort_by, liked_only
):
    """Render the pagination controls."""
    with tag.div("flex justify-end gap-4 p-4"):
        if current_page > 1:
            with tag.a(
                Styles.pagination_button,
                href=make_gallery_url(current_page - 1, sort_by, liked_only),
            ):
                text("← Previous")

        with tag.span(Styles.pagination_text):
            text(f"Page {current_page} of {total_pages}")

        if current_page < total_pages:
            with tag.a(
                Styles.pagination_button,
                href=make_gallery_url(current_page + 1, sort_by, liked_only),
            ):
                text("Next →")


def render_sort_options(sort_by, liked_only):
    """Render the sort options."""
    with tag.div("flex items-center gap-6"):
        # Sort controls group
        with tag.div("flex items-center gap-2"):
            with tag.span("text-xs text-neutral-600"):
                text("Sort by:")
            # Sort buttons group
            with tag.div("flex"):
                # Sort by recency
                with tag.a(
                    Styles.sort_button_active
                    if sort_by == "recency"
                    else Styles.sort_button,
                    href=make_gallery_url(1, "recency", liked_only),
                ):
                    text("Most Recent")

                # Sort by image count
                with tag.a(
                    Styles.sort_button_active
                    if sort_by == "image_count"
                    else Styles.sort_button,
                    href=make_gallery_url(1, "image_count", liked_only),
                ):
                    text("Most Generated")

        # Filter controls
        with tag.div("flex items-center gap-2"):
            with tag.span("text-xs text-neutral-600"):
                text("Filters:")
            # Liked filter
            with tag.a(
                Styles.filter_button_active
                if liked_only
                else Styles.filter_button,
                href=make_gallery_url(1, sort_by, not liked_only),
            ):
                with tag.span("text-sm"):
                    text("♥")
                text("Liked Only")


@html.a(
    Styles.button_secondary,
    "bg-amber-100 hover:bg-amber-200",
    "flex items-center gap-1",
)
def render_slideshow_link():
    attr("href", app.url_path_for("slideshow_liked"))
    with tag.span("text-sm"):
        text("♥")
    text("Slideshow")


@html.button(
    Styles.button_secondary,
    "bg-red-100 hover:bg-red-200",
    "flex items-center gap-1",
    "ml-2",
)
def render_delete_unliked_button():
    attr("hx-post", app.url_path_for("delete_unliked_images"))
    attr("hx-swap", "outerHTML")
    attr(
        "hx-confirm",
        "This will permanently delete all unliked images. Continue?",
    )
    with tag.span("text-sm"):
        text("🗑️")
    text("Delete Unliked")
