import os
from contextlib import contextmanager
from typing import List, Optional, Tuple
from urllib.parse import urlencode

from tagflow import attr, html, tag, text

from slopbox.base import (
    ASPECT_TO_RECRAFT,
    DEFAULT_MODEL,
    MODELS,
)
from slopbox.fastapi import app
from slopbox.model import Image, ImageSpec, split_prompt
from slopbox.ui import Styles


@html.div(
    "flex flex-col",
    "gap-2 p-2",
    "bg-neutral-100",
    "flex-1 min-w-[300px]",
)
def render_prompt_pills(image: Image):
    """Render the prompt pills for an image."""
    # Prompt
    with tag.div("flex flex-wrap gap-2"):
        for part in split_prompt(image.spec.prompt):
            with tag.span(
                "bg-neutral-200",
                "px-2 py-1",
                "rounded text-sm",
            ):
                text(part)

    # Model and aspect ratio info
    with tag.div("flex gap-4 text-xs text-neutral-500 mt-2"):
        with tag.span():
            text(f"Model: {image.spec.model}")
        with tag.span():
            text(f"Aspect: {image.spec.aspect_ratio}")

    # Action buttons
    with tag.div("flex gap-2 mt-2"):
        with tag.button(
            "text-xs",
            "px-2 py-1",
            "bg-neutral-200 hover:bg-neutral-300",
            "rounded",
            hx_post=app.url_path_for("copy_prompt", uuid_str=image.uuid),
            hx_target="#prompt-form",
            hx_swap="outerHTML",
        ):
            text("Copy Prompt")

        with tag.button(
            "text-xs",
            "px-2 py-1",
            "bg-neutral-200 hover:bg-neutral-300",
            "rounded",
            hx_post=app.url_path_for("regenerate", spec_id=image.spec.id),
            hx_target="#image-container",
            hx_swap="afterbegin settle:0.5s",
        ):
            text("Regenerate")


def render_image_or_status(image: Image):
    """Render just the image or its status indicator."""

    if image.status == "complete" and image.filepath:
        render_complete_image(image)
    elif image.status == "pending":
        render_pending_image(image)
    else:
        render_error_image(image)


def render_pending_image(image):
    # Calculate aspect ratio style based on the spec
    ratio_parts = [float(x) for x in image.spec.aspect_ratio.split(":")]
    aspect_ratio = ratio_parts[0] / ratio_parts[1]
    # For wide/landscape images, fix the width. For tall/portrait images, fix the height
    size_classes = "w-256" if aspect_ratio >= 1 else "h-256"
    aspect_style = f"aspect-[{image.spec.aspect_ratio.replace(':', '/')}]"

    with tag.div(
        size_classes,
        aspect_style,
        "bg-white",
        "p-2",
        "shadow-xl shadow-neutral-500",
        "border border-neutral-500",
        "z-10",
        "flex items-center justify-center",
    ):
        attr("hx-get", app.url_path_for("check_status", generation_id=image.uuid))
        attr("hx-trigger", "load delay:3s")
        attr("hx-swap", "outerHTML")
        with tag.span("text-gray-500"):
            text("Generating..." if image.status == "pending" else "Error")


def render_complete_image(image: Image):
    with tag.div(
        "relative group cursor-pointer",
        hx_post=app.url_path_for("toggle_like_endpoint", image_uuid=image.uuid),
        hx_target=f"#like-indicator-{image.uuid}",
        hx_swap="outerHTML",
    ):
        render_like_affordance(image)
        with tag.img(
            "max-w-256 max-h-256",
            "object-contain flex-0",
            "bg-white p-2",
            "shadow-xl shadow-neutral-500",
            "border-amber-200 border-4" if image.liked else "border border-neutral-500",
            "z-10",
            src=f"/images/{os.path.basename(image.filepath)}",
            alt=image.spec.prompt,
        ):
            pass


def render_like_affordance(image):
    with tag.div(
        "absolute top-2 right-2",
        "p-2 rounded-full",
        "opacity-0 group-hover:opacity-100 transition-opacity",
        "z-20 pointer-events-none",
        "bg-amber-100 text-amber-600"
        if image.liked
        else "bg-white/80 text-neutral-600",
        id=f"like-indicator-{image.uuid}",
    ):
        with tag.span("text-xl"):
            text("♥")


def render_error_image(image):
    with tag.div(
        "w-256",
        "aspect-square",
        "bg-white",
        "p-2",
        "shadow-xl shadow-neutral-500",
        "border border-red-500",
        "z-10",
        "flex items-center justify-center",
    ):
        with tag.span("text-red-500"):
            text("Error")


@html.div("flex flex-row p-2")
def render_single_image(image: Image):
    """Render a single image card with appropriate HTMX attributes."""
    attr("id", f"generation-{image.uuid}")
    render_image_or_status(image)
    render_prompt_pills(image)


@html.div(
    "w-2xl shrink-0",
    "bg-neutral-200 p-2",
    "border-neutral-400",
    "relative",
    "sticky top-2",
)
def render_spec_header(spec: ImageSpec):
    """Render the header for a spec showing prompt and generation options."""
    # Actions
    with tag.div("flex gap-2 mb-2 justify-between"):
        render_spec_action_buttons(spec)

        with tag.div("flex gap-4 items-baseline text-neutral-600"):
            with tag.span():
                text(spec.model)
            with tag.span():
                text(spec.aspect_ratio)
            with tag.span("text-neutral-800 font-mono"):
                text(f"#{spec.id}")

    # Prompt display
    with tag.div("flex flex-wrap gap-2"):
        for part in split_prompt(spec.prompt):
            with tag.span(
                "bg-neutral-100",
                "px-3 py-1",
                "rounded-md text-sm",
                "border-l-4 border-b border-r border-neutral-400",
                "text-neutral-800",
            ):
                text(part)


@html.div("flex gap-2")
def render_spec_action_buttons(spec):
    render_copy_settings_button(spec)
    render_generate_new_button(spec)
    render_slideshow_button(spec)


def render_copy_settings_button(spec):
    with tag.button(
        Styles.spec_action_button,
        hx_post=app.url_path_for("copy_spec", spec_id=spec.id),
        hx_target="#prompt-form",
        hx_swap="outerHTML",
    ):
        text("Copy Settings")


def render_generate_new_button(spec):
    with tag.button(
        Styles.spec_action_button,
        hx_post=app.url_path_for("regenerate", spec_id=spec.id),
        hx_target=f"#spec-images-{spec.id}",
        hx_swap="afterbegin settle:0.5s",
    ):
        text("Generate New")


def render_slideshow_button(spec):
    with tag.a(
        Styles.spec_action_button,
        href=app.url_path_for("slideshow") + "?" + urlencode({"spec_id": spec.id}),
    ):
        text("Slideshow")


@html.div(
    "flex flex-wrap",
    "gap-4",
)
def render_spec_images(spec: ImageSpec, images: List[Image], liked_only: bool = False):
    """Render the image grid for a spec."""
    attr("id", f"spec-images-{spec.id}")

    # Filter liked images if needed
    filtered_images = [img for img in images if not liked_only or img.liked]

    # Show first 4 images
    for image in filtered_images[:4]:
        render_image_or_status(image)

    # If there are more images, show them in a collapsible section
    if len(filtered_images) > 4:
        with tag.details("w-full mt-4"):
            with tag.summary(
                "cursor-pointer text-sm text-neutral-600 hover:text-neutral-800"
            ):
                text(f"Show {len(filtered_images) - 4} more images...")
            with tag.div("flex flex-wrap gap-4 mt-4"):
                for image in filtered_images[4:]:
                    render_image_or_status(image)


@html.div("w-full px-2 mb-8 flex flex-col items-start gap-2")
def render_spec_block(spec: ImageSpec, images: List[Image], liked_only: bool = False):
    """Render a complete spec block with header and images."""
    render_spec_header(spec)
    render_spec_images(spec, images, liked_only)


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


def render_pagination_controls(current_page, total_pages, sort_by, liked_only):
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
                Styles.filter_button_active if liked_only else Styles.filter_button,
                href=make_gallery_url(1, sort_by, not liked_only),
            ):
                with tag.span("text-sm"):
                    text("♥")
                text("Liked Only")


@html.div(
    "flex flex-col gap-2",
    "w-full",
    id="prompt-inputs",
)
def render_prompt_inputs(prompt):
    # If there's an existing prompt, split it into parts
    prompt_parts = split_prompt(prompt) if prompt else []
    # If no prompt parts or empty prompt, just add one empty input
    if not prompt_parts:
        prompt_parts = [""]

    # Render existing prompt parts
    for i, part in enumerate(prompt_parts):
        render_prompt_part_input(i, part)

    next_index = len(prompt_parts)
    with tag.button(
        Styles.button_secondary,
        type="button",
        hx_get=app.url_path_for("get_prompt_part", index=next_index),
        hx_target="this",
        hx_swap="beforebegin",
    ):
        text("Add prompt part")

    with tag.button(
        Styles.button_primary,
        type="submit",
    ):
        text("Generate")


@html.div("flex gap-2 w-full")
def render_prompt_part_input(index: int = 0, content: str = ""):
    """Render a single prompt part input with remove button."""
    with tag.textarea(
        Styles.input_primary,
        name=f"prompt_part_{index}",
        placeholder="Enter part of the prompt",
    ):
        text(content)
    with tag.button(
        type="button",
        onclick="this.parentElement.remove()",
    ):
        text("×")


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

    attr("id", "slideshow-content")
    attr("hx-get", next_url)
    attr("hx-target", "#slideshow-content")
    attr("hx-swap", "outerHTML")
    attr("hx-trigger", "every 1s")

    if image and image.status == "complete" and image.filepath:
        with tag.div(
            "bg-white rounded-lg shadow-2xl shadow-neutral-700",
            id="image-container",
        ):
            # Image with padding
            with tag.img(
                "object-contain h-screen",
                src=f"/images/{os.path.basename(image.filepath)}",
                alt=image.spec.prompt,
            ):
                pass
    else:
        with tag.div("text-white text-2xl"):
            text("No images available")


def render_cdn_includes():
    with tag.script(src="https://unpkg.com/@tailwindcss/browser@4"):
        pass
    with tag.script(src="https://unpkg.com/htmx.org@2.0.4"):
        pass


@contextmanager
def render_base_layout():
    with tag.html(lang="en"):
        with tag.head():
            with tag.title():
                text("Slopbox")
            render_cdn_includes()
        with tag.body(classes="bg-neutral-400 flex h-screen"):
            yield


@html.div("flex flex-col gap-2")
def render_generation_options(model: str = None, aspect_ratio: str = None):
    # Model selection
    with tag.fieldset("flex flex-col gap-2"):
        with tag.span("text-xs text-neutral-600"):
            text("Model")
        with tag.div("flex gap-4"):
            for model_name, model_id in MODELS.items():
                is_checked = model_id == model if model else model_id == DEFAULT_MODEL
                with tag.div("flex items-center"):
                    with tag.input(
                        [
                            "relative size-4",
                            "appearance-none rounded-full",
                            "border border-neutral-300 bg-white",
                            "before:absolute before:inset-1",
                            "before:rounded-full before:bg-white",
                            "checked:border-neutral-600 checked:bg-neutral-600",
                            "focus-visible:outline focus-visible:outline-2",
                            "focus-visible:outline-offset-2 focus-visible:outline-neutral-600",
                            "[&:not(:checked)]:before:hidden",
                        ],
                        id=f"model-{model_id}",
                        type="radio",
                        name="model",
                        value=model_id,
                        checked=is_checked,
                    ):
                        pass
                    with tag.label(
                        "ml-3 text-sm font-medium text-neutral-900",
                        for_=f"model-{model_id}",
                    ):
                        text(model_name)

    # Aspect ratio selection
    with tag.fieldset("flex flex-col gap-2"):
        with tag.span("text-xs text-neutral-600"):
            text("Aspect Ratio")
        with tag.div("flex gap-2 justify-start"):
            for ratio in ASPECT_TO_RECRAFT.keys():
                is_checked = ratio == aspect_ratio if aspect_ratio else ratio == "1:1"
                # Calculate preview dimensions
                w, h = map(float, ratio.split(":"))
                preview_size = 48  # Base size in pixels
                if w > h:
                    scaled_width = preview_size
                    scaled_height = int(preview_size * (h / w))
                else:
                    scaled_height = preview_size
                    scaled_width = int(preview_size * (w / h))

                with tag.label(
                    "flex flex-col items-center justify-end cursor-pointer relative p-2",
                ):
                    with tag.input(
                        "appearance-none absolute peer",
                        type="radio",
                        name="aspect_ratio",
                        value=ratio,
                        checked=is_checked,
                    ):
                        pass
                    # Preview box that changes style when radio is checked
                    with tag.div(
                        "rounded",
                        "transition-all duration-150",
                        # Selected state via peer
                        "peer-checked:bg-neutral-800",
                        "peer-checked:ring-2 peer-checked:ring-neutral-800",
                        # Unselected state
                        "bg-neutral-500",
                        "ring-1 ring-neutral-500",
                        # Hover states
                        "hover:bg-neutral-600 hover:ring-neutral-600",
                        style=f"width: {scaled_width}px; height: {scaled_height}px",
                    ):
                        pass
                    with tag.span("mt-1 text-xs text-neutral-600"):
                        text(ratio)


@html.form(
    "flex flex-col gap-2 p-4",
    hx_target="#prompt-form",
    hx_include="[name^='prompt_part_']",
    hx_swap="outerHTML",
)
def render_prompt_modification_form():
    attr("hx-post", app.url_path_for("modify_prompt"))
    with tag.textarea(
        Styles.input_primary,
        type="text",
        name="modification",
        placeholder="How to modify the prompt (e.g., 'make it more detailed')",
        rows="4",
    ):
        pass

    with tag.button(
        Styles.button_primary,
        type="submit",
    ):
        text("Modify")


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


def render_prompt_form_dropdown(
    prompt: str = None, model: str = None, aspect_ratio: str = None
):
    """Render the prompt form in a dropdown button."""
    with tag.details("relative"):
        with tag.summary(Styles.button_primary):
            text("New Image")

        # Dropdown content
        with tag.div(
            "absolute top-full right-0 mt-4",
            "bg-neutral-200",
            "shadow-lg",
            "border border-neutral-400",
            "w-[500px]",
            "z-50",
        ):
            render_prompt_form_content(prompt, model, aspect_ratio)


@html.div(id="prompt-form")
def render_prompt_form_content(
    prompt: str = None, model: str = None, aspect_ratio: str = None
):
    """Render the prompt form content without the container."""
    with tag.form(
        "flex flex-col gap-4 p-4",
        hx_post=app.url_path_for("generate"),
        hx_target="#gallery-container",
        hx_swap="afterbegin settle:0.5s",
        hx_disabled_elt="input, button, select",
    ):
        render_generation_options(model, aspect_ratio)
        render_prompt_inputs(prompt)

    render_prompt_modification_form()
