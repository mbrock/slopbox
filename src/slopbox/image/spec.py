from typing import List
from urllib.parse import urlencode

from tagflow import attr, html, tag, text

from slopbox.fastapi import app
from slopbox.image.img import render_image_or_status
from slopbox.model import Image, ImageSpec, split_prompt
from slopbox.ui import Styles


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
            with tag.span():
                style_name = spec.style.split("/")[-1].replace("_", " ").title() if "/" in spec.style else spec.style.replace("_", " ").title()
                text(f"{style_name}")
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


@html.div(
    "flex flex-col",
    "gap-2 p-2",
    "bg-neutral-100",
    "flex-1 min-w-[300px]",
)
def render_prompt_pills(image: Image):
    """Render the prompt pills for an image."""
    assert image.spec is not None

    # Prompt
    with tag.div("flex flex-wrap gap-2"):
        for part in split_prompt(image.spec.prompt):
            with tag.span(
                "bg-neutral-200",
                "px-2 py-1",
                "rounded text-sm",
            ):
                text(part)

    # Model, aspect ratio, and style info
    with tag.div("flex gap-4 text-xs text-neutral-500 mt-2"):
        with tag.span():
            text(f"Model: {image.spec.model}")
        with tag.span():
            text(f"Aspect: {image.spec.aspect_ratio}")
        with tag.span():
            style_name = image.spec.style.split("/")[-1].replace("_", " ").title() if "/" in image.spec.style else image.spec.style.replace("_", " ").title()
            text(f"Style: {style_name}")

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


@html.div("flex flex-row p-2")
def render_single_image(image: Image):
    """Render a single image card with appropriate HTMX attributes."""
    attr("id", f"generation-{image.uuid}")
    render_image_or_status(image)
    render_prompt_pills(image)


@html.div("flex gap-2")
def render_spec_action_buttons(spec):
    render_copy_settings_button(spec)
    render_generate_new_button(spec)
    render_slideshow_button(spec)


def render_generate_new_button(spec):
    with tag.button(
        Styles.spec_action_button,
        hx_post=app.url_path_for("regenerate", spec_id=spec.id),
        hx_target=f"#spec-images-{spec.id}",
        hx_swap="afterbegin settle:0.5s",
    ):
        text("Generate New")


def render_copy_settings_button(spec):
    with tag.button(
        Styles.spec_action_button,
        hx_post=app.url_path_for("copy_spec", spec_id=spec.id),
        hx_target="#prompt-form",
        hx_swap="outerHTML",
    ):
        text("Copy Settings")


def render_slideshow_button(spec):
    with tag.a(
        Styles.spec_action_button,
        href=app.url_path_for("slideshow") + "?" + urlencode({"spec_id": spec.id}),
    ):
        text("Slideshow")
