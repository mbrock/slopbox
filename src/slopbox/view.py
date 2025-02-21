import os
from contextlib import contextmanager
from typing import List, Optional, Tuple
from urllib.parse import urlencode

from tagflow import attr, classes, html, tag, text

from slopbox.base import (
    ASPECT_TO_RECRAFT,
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
    with tag.div(classes=["flex flex-wrap gap-2"]):
        for part in split_prompt(image.spec.prompt):
            with tag.span(
                classes=["bg-neutral-200", "px-2 py-1", "rounded text-sm"],
            ):
                text(part)

    # Model and aspect ratio info
    with tag.div(classes=["flex gap-4", "text-xs text-neutral-500 mt-2"]):
        with tag.span():
            text(f"Model: {image.spec.model}")
        with tag.span():
            text(f"Aspect: {image.spec.aspect_ratio}")

    # Action buttons
    with tag.div(classes=["flex gap-2 mt-2"]):
        with tag.button(
            classes=[
                "text-xs",
                "px-2 py-1",
                "bg-neutral-200 hover:bg-neutral-300",
                "rounded",
            ],
            hx_post=app.url_path_for("copy_prompt", uuid_str=image.uuid),
            hx_target="#prompt-container",
        ):
            text("Copy Prompt")

        with tag.button(
            classes=[
                "text-xs",
                "px-2 py-1",
                "bg-neutral-200 hover:bg-neutral-300",
                "rounded",
            ],
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
        classes=[
            *size_classes,
            aspect_style,
            "bg-white",
            "p-2",
            "shadow-xl shadow-neutral-500",
            "border border-neutral-500",
            "z-10",
            "flex items-center justify-center",
        ],
    ):
        attr("hx-get", app.url_path_for("check_status", generation_id=image.uuid))
        attr("hx-trigger", "load delay:1s")
        attr("hx-swap", "outerHTML")
        with tag.span(classes="text-gray-500"):
            text("Generating..." if image.status == "pending" else "Error")


def render_complete_image(image):
    with tag.div(
        classes=["relative group", "cursor-pointer"],
        hx_post=app.url_path_for("toggle_like_endpoint", image_uuid=image.uuid),
        hx_target=f"#like-indicator-{image.uuid}",
        hx_swap="outerHTML",
    ):
        render_like_affordance(image)
        with tag.img(
            src=f"/images/{os.path.basename(image.filepath)}",
            alt=image.spec.prompt,
            classes=[
                "max-w-256 max-h-256",
                "object-contain flex-0",
                "bg-white p-2",
                "shadow-xl shadow-neutral-500",
                "border-amber-200 border-4"
                if image.liked
                else "border border-neutral-500",
                "z-10",
            ],
        ):
            pass


def render_like_affordance(image):
    with tag.div(
        id=f"like-indicator-{image.uuid}",
        classes=[
            "absolute top-2 right-2",
            "p-2 rounded-full",
            "opacity-0 group-hover:opacity-100 transition-opacity",
            "z-20 pointer-events-none",
            "bg-amber-100 text-amber-600"
            if image.liked
            else "bg-white/80 text-neutral-600",
        ],
    ):
        with tag.span(classes="text-xl"):
            text("♥")


def render_error_image(image):
    with tag.div(
        classes=[
            "w-256",
            "aspect-square",
            "bg-white",
            "p-2",
            "shadow-xl shadow-neutral-500",
            "border border-red-500",
            "z-10",
            "flex items-center justify-center",
        ],
    ):
        with tag.span(classes="text-red-500"):
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
    with tag.div(classes=["flex gap-2 mb-2 justify-between"]):
        render_spec_action_buttons(spec)

        with tag.div(classes=["flex gap-4 items-baseline text-neutral-600"]):
            with tag.span():
                text(spec.model)
            with tag.span():
                text(spec.aspect_ratio)
            with tag.span(classes=["text-neutral-800 font-mono"]):
                text(f"#{spec.id}")

    # Prompt display
    with tag.div(classes=["flex flex-wrap gap-2"]):
        for part in split_prompt(spec.prompt):
            with tag.span(
                classes=[
                    "bg-neutral-100",
                    "px-3 py-1",
                    "rounded-md text-sm",
                    "border-l-4 border-b border-r border-neutral-400",
                    "text-neutral-800",
                ],
            ):
                text(part)


@html.div(classes=["flex gap-2"])
def render_spec_action_buttons(spec):
    render_copy_settings_button(spec)
    render_generate_new_button(spec)
    render_slideshow_button(spec)


def render_copy_settings_button(spec):
    with tag.button(
        classes=Styles.spec_action_button,
        hx_post=app.url_path_for("copy_spec", spec_id=spec.id),
        hx_target="#prompt-container",
    ):
        text("Copy Settings")


def render_generate_new_button(spec):
    with tag.button(
        classes=Styles.spec_action_button,
        hx_post=app.url_path_for("regenerate", spec_id=spec.id),
        hx_target=f"#spec-images-{spec.id}",
        hx_swap="afterbegin settle:0.5s",
    ):
        text("Generate New")


def render_slideshow_button(spec):
    with tag.a(
        classes=Styles.spec_action_button,
        href=app.url_path_for("slideshow") + "?" + urlencode({"spec_id": spec.id}),
    ):
        text("Slideshow")


@html.div(
    "flex flex-wrap",
    "gap-4",
    "px-4",
)
def render_spec_images(spec: ImageSpec, images: List[Image]):
    """Render the image grid for a spec."""
    attr("id", f"spec-images-{spec.id}")
    for image in images:
        render_image_or_status(image)


@html.div("w-full px-2 mb-8 flex flex-row items-start")
def render_spec_block(spec: ImageSpec, images: List[Image]):
    """Render a complete spec block with header and images."""
    render_spec_header(spec)
    render_spec_images(spec, images)


@html.div(
    "h-full overflow-y-auto",
    "flex-1",
    "flex flex-col items-stretch",
    "gap-1",
    id="gallery-container",
)
def render_image_gallery(
    specs_with_images: List[Tuple[ImageSpec, List[Image]]],
    current_page: int,
    total_pages: int,
    sort_by: str = "recency",
    min_images: int = 0,
    liked_only: bool = False,
):
    """Generate the HTML for the image gallery."""
    render_gallery_controls(sort_by, min_images, liked_only)
    render_pagination_controls(
        current_page, total_pages, sort_by, min_images, liked_only
    )

    for spec, images in specs_with_images:
        render_spec_block(spec, images)


def make_gallery_url(page: int, sort_by: str, min_images: int, liked_only: bool) -> str:
    """Construct a gallery URL with the given parameters."""
    return (
        app.url_path_for("gallery")
        + "?"
        + urlencode(
            {
                "page": page,
                "sort_by": sort_by,
                "min_images": min_images,
                "liked_only": str(liked_only).lower(),
            }
        )
    )


@html.div("flex justify-end gap-4")
def render_pagination_controls(
    current_page, total_pages, sort_by, min_images, liked_only
):
    if total_pages > 1:
        if current_page > 1:
            render_previous_page_button(current_page, sort_by, min_images, liked_only)

        render_page_indicator(current_page, total_pages)

        if current_page < total_pages:
            render_next_page_button(current_page, sort_by, min_images, liked_only)


def render_previous_page_button(current_page, sort_by, min_images, liked_only):
    with tag.button(
        classes=Styles.pagination_button,
        hx_get=make_gallery_url(current_page - 1, sort_by, min_images, liked_only),
        hx_target="#gallery-container",
    ):
        text("Previous")


def render_next_page_button(current_page, sort_by, min_images, liked_only):
    with tag.button(
        classes=Styles.pagination_button,
        hx_get=make_gallery_url(current_page + 1, sort_by, min_images, liked_only),
        hx_target="#gallery-container",
    ):
        text("Next")


def render_page_indicator(current_page, total_pages):
    with tag.span(classes=Styles.pagination_text):
        text(f"Page {current_page} of {total_pages}")


@html.div(
    "flex justify-between items-center",
    "bg-neutral-200",
    "px-4 py-1",
)
def render_gallery_controls(sort_by, min_images, liked_only):
    render_sort_options(sort_by, min_images, liked_only)
    render_image_filters(sort_by, min_images, liked_only)


@html.div("flex items-center gap-4")
def render_image_filters(sort_by, min_images, liked_only):
    with tag.span(classes=["text-sm font-medium"]):
        text("Filter:")
    with tag.div(classes=["flex gap-2"]):
        render_image_count_filters(sort_by, min_images, liked_only)
        render_liked_filter(sort_by, min_images, liked_only)
        render_slideshow_link()


@html.a(
    classes=[
        "text-xs",
        "px-3 py-1",
        "bg-amber-100 hover:bg-amber-200",
        "rounded",
        "flex items-center gap-1",
    ],
)
def render_slideshow_link():
    attr("href", app.url_path_for("slideshow"))
    with tag.span(classes="text-sm"):
        text("♥")
    text("Slideshow")


@html.a(
    classes=[
        "text-xs",
        "px-3 py-1",
        "rounded",
        "flex items-center gap-1",
    ],
)
def render_liked_filter(sort_by, min_images, liked_only):
    if liked_only:
        classes("bg-amber-600 text-white")
    else:
        classes("bg-amber-100 hover:bg-amber-200")

    url = make_gallery_url(1, sort_by, min_images, True)
    attr("href", url)
    attr("hx-get", url)
    attr("hx-target", "#gallery-container")

    with tag.span(classes="text-sm"):
        text("♥")
    text("Liked")


@html.div("flex items-center gap-4")
def render_sort_options(sort_by, min_images, liked_only):
    with tag.span(classes=["text-sm font-medium"]):
        text("Sort by:")
    with tag.div(classes=["flex gap-2"]):
        for sort_option in [("recency", "Most Recent"), ("image_count", "Most Images")]:
            with tag.a(
                classes=[
                    "text-xs px-3 py-1",
                    "rounded",
                    "bg-neutral-100 hover:bg-neutral-300",
                ],
                href=make_gallery_url(1, sort_option[0], min_images, liked_only),
                hx_get=make_gallery_url(1, sort_option[0], min_images, liked_only),
                hx_target="#gallery-container",
            ):
                text(sort_option[1])


@html.div("flex flex-col gap-1")
def render_model_selection(model):
    with tag.label(classes=["text-sm font-medium"]):
        text("Model")
    with tag.div(classes=["flex flex-wrap gap-4"]):
        for model_name, model_id in MODELS.items():
            with tag.label(classes=["flex items-center gap-2", "text-xs"]):
                with tag.input(
                    classes="w-4 h-4",
                    type="radio",
                    name="model",
                    value=model_id,
                    checked=(
                        model_id == model
                        if model
                        else model_id == MODELS["Flux 1.1 Pro Ultra"]
                    ),
                ):
                    pass
                text(model_name)


@html.div(
    classes=["flex flex-col gap-2", "w-full p-2"],
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
        type="button",
        classes=Styles.button_secondary,
        hx_get=app.url_path_for("get_prompt_part", index=next_index),
        hx_target="this",
        hx_swap="beforebegin",
    ):
        text("Add prompt part")

    with tag.button(
        type="submit",
        classes=Styles.button_primary,
    ):
        text("Generate")


@html.div(classes=["flex gap-2 w-full"])
def render_prompt_part_input(index: int = 0, content: str = ""):
    """Render a single prompt part input with remove button."""
    rows_by_char_count = max(1, len(content) // 70)
    with tag.textarea(
        name=f"prompt_part_{index}",
        placeholder="Enter part of the prompt",
        classes=Styles.input_primary,
        rows=f"{rows_by_char_count}",
    ):
        text(content)
    with tag.button(
        type="button",
        onclick="this.parentElement.remove()",
    ):
        text("×")


@html.div(
    classes=[
        "flex flex-col",
        "self-start",
        "relative",
        "gap-4 px-2",
        "bg-neutral-200",
        #        "border-1 border-t-0 border-neutral-500",
        #        "shadow-xl",
    ],
    id="prompt-container",
)
def render_prompt_form(prompt: str = None, model: str = None, aspect_ratio: str = None):
    """Render the prompt form with generation options and modification form."""
    with tag.details(classes=["w-full"], open=True):
        with tag.summary(
            classes=[
                "cursor-pointer",
                "text-sm",
                "font-medium",
                "p-2",
            ]
        ):
            text("New")
        # Main generation form
        with tag.form(
            classes=["flex flex-col gap-4", "w-full", "mt-2"],
            hx_post=app.url_path_for("generate"),
            hx_target="#gallery-container",
            hx_swap="afterbegin settle:0.5s",
            hx_disabled_elt="input, button, select",
        ):
            render_generation_options(model, aspect_ratio)
            render_prompt_inputs(prompt)
        render_prompt_modification_form()


@html.div(
    classes=[
        "h-screen w-screen",
        "flex flex-col",
        "items-center justify-center",
        "relative",
        "bg-stone-900",
    ],
    id="slideshow-container",
)
def render_slideshow(
    image: Optional[Image],
    image_count: Optional[int] = None,
    spec_id: Optional[int] = None,
):
    """Render the slideshow view with a single image and auto-refresh."""
    render_slideshow_content(image, image_count, spec_id)


@html.div(classes=["flex flex-col", "items-center justify-center", "relative"])
def render_slideshow_content(
    image: Optional[Image],
    image_count: Optional[int] = None,
    spec_id: Optional[int] = None,
):
    """Render just the content of the slideshow that needs to be updated."""
    next_url = app.url_path_for("slideshow_next")
    if spec_id is not None:
        next_url += "?" + urlencode({"spec_id": spec_id})

    attr("id", "slideshow-content")
    attr("hx-get", next_url)
    attr("hx-target", "#slideshow-content")
    attr("hx-swap", "outerHTML transition:true")
    attr("hx-trigger", "every 1s")

    if image and image.status == "complete" and image.filepath:
        with tag.div(
            id="image-container",
            classes=["bg-white", "rounded-lg", "shadow-2xl shadow-neutral-700"],
        ):
            # Image with padding
            with tag.img(
                classes=["object-contain", "h-screen"],
                src=f"/images/{os.path.basename(image.filepath)}",
                alt=image.spec.prompt,
            ):
                pass
    else:
        with tag.div(classes=["text-white", "text-2xl"]):
            text("No images available")


@html.div("flex gap-2")
def render_image_count_filters(sort_by, min_images, liked_only):
    for count in [0, 2, 4, 8]:
        url = make_gallery_url(1, sort_by, count, liked_only)
        with tag.a(
            href=url,
            hx_get=url,
            hx_target="#gallery-container",
        ):
            text("All" if count == 0 else f"{count}+")


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


@html.div(classes=["flex flex-col gap-4", "py-2 px-4"])
def render_generation_options(model: str = None, aspect_ratio: str = None):
    render_model_selection(model)
    render_aspect_ratio_selection(aspect_ratio)
    render_style_selection()


@html.div(classes=["flex flex-col gap-1"])
def render_style_selection():
    with tag.label(classes=["text-sm font-medium"]):
        text("Style")
    with tag.div(classes=["flex gap-4"]):
        for style in ["natural", "studio", "illustration", "flash"]:
            with tag.label(classes=["flex items-center gap-2", "text-xs"]):
                with tag.input(
                    classes="w-4 h-4",
                    type="radio",
                    name="style",
                    value=style,
                    checked=(style == "natural"),
                ):
                    pass
                text(style.capitalize())


@html.div(classes=["flex flex-col gap-1"])
def render_aspect_ratio_selection(aspect_ratio):
    with tag.label(classes=["text-sm font-medium"]):
        text("Aspect Ratio")
    with tag.div(classes=["flex flex-wrap gap-4"]):
        for ratio in ASPECT_TO_RECRAFT.keys():
            with tag.label(classes=["flex items-center gap-2", "text-xs"]):
                with tag.input(
                    classes="w-4 h-4",
                    type="radio",
                    name="aspect_ratio",
                    value=ratio,
                    checked=(ratio == aspect_ratio if aspect_ratio else ratio == "1:1"),
                ):
                    pass
                text(ratio)


@html.form(
    classes=["flex flex-col gap-2", "p-2"],
    hx_target="#prompt-container",
    hx_include="[name^='prompt_part_']",
    hx_swap="outerHTML",
)
def render_prompt_modification_form():
    attr("hx-post", app.url_path_for("modify_prompt"))
    with tag.textarea(
        type="text",
        name="modification",
        placeholder="How to modify the prompt (e.g., 'make it more detailed')",
        classes=Styles.input_primary,
        rows="4",
    ):
        pass

    with tag.button(
        type="submit",
        classes=Styles.button_primary,
    ):
        text("Modify")
