import os
from contextlib import contextmanager
from typing import List, Tuple

from tagflow import attr, tag, text

from yap.base import (
    ASPECT_TO_RECRAFT,
    MODELS,
)
from yap.model import Image, ImageSpec


def button_primary():
    return "font-semibold text-sm bg-slate-200 px-2 py-1 text-gray-800 shadow-sm border-1 border-neutral-500 hover:bg-slate-300"


def button_secondary():
    return "bg-white bg-neutral-300 px-2 py-1 text-xs text-neutral-800 ring-1 ring-inset ring-neutral-400 hover:bg-neutral-100 hover:text-neutral-900"


def button_danger():
    return "bg-white text-sm border-1 border-neutral-500 text-red-500 px-2"


def button_action():
    return (
        "bg-black text-white px-6 py-2 disabled:opacity-50 disabled:cursor-not-allowed"
    )


def input_primary():
    return "flex-1 border border-neutral-500 px-2 bg-white text-sm placeholder:text-neutral-600 placeholder:italic"


def container_primary():
    return "bg-neutral-300"


def flex_row():
    return "flex flex-row flex-wrap gap-2"


def flex_col():
    return "flex flex-col"


def render_prompt_pills(image: Image):
    """Render the prompt pills for an image."""
    with tag.div(
        classes="flex flex-col gap-2 p-2 bg-neutral-100 flex-1 min-w-[300px]",
    ):
        # Prompt
        with tag.div(classes="flex flex-wrap gap-2"):
            for part in image.spec.prompt.split(","):
                with tag.span(classes="bg-neutral-200 px-2 py-1 rounded text-sm"):
                    text(part.strip())

        # Model and aspect ratio info
        with tag.div(classes="flex gap-4 text-xs text-neutral-500 mt-2"):
            with tag.span():
                text(f"Model: {image.spec.model}")
            with tag.span():
                text(f"Aspect: {image.spec.aspect_ratio}")

        # Action buttons
        with tag.div(classes="flex gap-2 mt-2"):
            with tag.button(
                hx_post=f"/copy-prompt/{image.uuid}",
                hx_target="#prompt-container",
                classes="text-xs px-2 py-1 bg-neutral-200 hover:bg-neutral-300 rounded",
            ):
                text("Copy Prompt")

            # Add regenerate button that creates a new generation with the same spec
            with tag.button(
                hx_post=f"/regenerate/{image.spec.id}",
                hx_target="#image-container",
                hx_swap="afterbegin settle:0.5s",
                classes="text-xs px-2 py-1 bg-neutral-200 hover:bg-neutral-300 rounded",
            ):
                text("Regenerate")


def render_image_or_status(image: Image):
    """Render just the image or its status indicator."""
    # Calculate aspect ratio style based on the spec
    ratio_parts = [float(x) for x in image.spec.aspect_ratio.split(":")]
    aspect_ratio = ratio_parts[0] / ratio_parts[1]
    # For wide/landscape images, fix the width. For tall/portrait images, fix the height
    size_classes = "w-256" if aspect_ratio >= 1 else "h-256"
    aspect_style = f"aspect-[{image.spec.aspect_ratio.replace(':', '/')}]"

    if image.status == "complete" and image.filepath:
        with tag.img(
            src=f"/images/{os.path.basename(image.filepath)}",
            alt=image.spec.prompt,
            classes="max-w-256 max-h-256 object-contain flex-0 bg-white p-2 shadow-xl shadow-neutral-500 z-10 border border-neutral-500",
        ):
            pass
    else:
        if image.status == "pending":
            with tag.div(
                classes=f"{size_classes} {aspect_style} bg-white p-2 shadow-xl shadow-neutral-500 z-10 border border-neutral-500 flex items-center justify-center",
            ):
                attr("hx-get", f"/check/{image.uuid}")
                attr("hx-trigger", "load delay:1s")
                attr("hx-swap", "outerHTML")
                with tag.span(classes="text-gray-500"):
                    text("Generating..." if image.status == "pending" else "Error")


def render_single_image(image: Image):
    """Render a single image card with appropriate HTMX attributes."""
    with tag.div(
        classes="flex p-2",
        id=f"generation-{image.uuid}",
    ):
        render_image_or_status(image)
        render_prompt_pills(image)


def render_spec_header(spec: ImageSpec):
    """Render the header for a spec showing prompt and generation options."""
    with tag.div(
        classes="w-full bg-neutral-200 p-4 rounded-t border border-neutral-400 relative"
    ):
        # Spec ID (subtle, top-right corner)
        with tag.div(classes="absolute top-1 right-2 text-xs text-neutral-400"):
            text(f"#{spec.id}")

        # Prompt display
        with tag.div(classes="flex flex-wrap gap-2 mb-3"):
            for part in spec.prompt.split(","):
                with tag.span(classes="bg-white px-3 py-1 rounded text-sm"):
                    text(part.strip())

        # Model and settings
        with tag.div(classes="flex gap-4 text-xs text-neutral-600"):
            with tag.span():
                text(f"Model: {spec.model}")
            with tag.span():
                text(f"Aspect: {spec.aspect_ratio}")

        # Actions
        with tag.div(classes="flex gap-2 mt-3"):
            with tag.button(
                hx_post=f"/copy-spec/{spec.id}",
                hx_target="#prompt-container",
                classes="text-xs px-3 py-1 bg-white hover:bg-neutral-100 rounded border border-neutral-400",
            ):
                text("Copy Settings")
            with tag.button(
                hx_post=f"/regenerate/{spec.id}",
                hx_target=f"#spec-images-{spec.id}",
                hx_swap="afterbegin settle:0.5s",
                classes="text-xs px-3 py-1 bg-white hover:bg-neutral-100 rounded border border-neutral-400",
            ):
                text("Generate New")


def render_spec_images(spec: ImageSpec, images: List[Image]):
    """Render the image grid for a spec."""
    with tag.div(
        id=f"spec-images-{spec.id}",
        classes="flex flex-wrap gap-4 p-4 bg-neutral-100 rounded-b border-x border-b border-neutral-400",
    ):
        for image in images:
            render_image_or_status(image)


def render_spec_block(spec: ImageSpec, images: List[Image]):
    """Render a complete spec block with header and images."""
    with tag.div(classes="w-full mb-8"):
        render_spec_header(spec)
        render_spec_images(spec, images)


def generate_gallery(
    specs_with_images: List[Tuple[ImageSpec, List[Image]]],
    current_page: int,
    total_pages: int,
):
    """Generate the HTML for the image gallery."""
    with tag.div(
        id="gallery-container",
        classes="h-full overflow-y-auto flex-1 flex flex-col items-stretch p-4 gap-8",
    ):
        # Specs and their images
        for spec, images in specs_with_images:
            render_spec_block(spec, images)

        # Pagination controls
        if total_pages > 1:
            with tag.div(
                classes="flex justify-center items-center gap-4 mt-8 sticky bottom-0 bg-neutral-300 p-4 rounded-full shadow-xl"
            ):
                # Previous page button
                if current_page > 1:
                    with tag.button(
                        hx_get=f"/gallery?page={current_page - 1}",
                        hx_target="#gallery-container",
                        classes="px-4 py-2 bg-white hover:bg-neutral-100 rounded shadow",
                    ):
                        text("Previous")

                # Page indicator
                with tag.span(classes="text-neutral-700"):
                    text(f"Page {current_page} of {total_pages}")

                # Next page button
                if current_page < total_pages:
                    with tag.button(
                        hx_get=f"/gallery?page={current_page + 1}",
                        hx_target="#gallery-container",
                        classes="px-4 py-2 bg-white hover:bg-neutral-100 rounded shadow",
                    ):
                        text("Next")


def render_prompt_inputs(prompt):
    with tag.div(
        id="prompt-inputs",
        classes="flex flex-col gap-2 w-full p-2",
    ):
        # If there's an existing prompt, split it into parts
        prompt_parts = prompt.split(",") if prompt else []
        # If no prompt parts or empty prompt, just add one empty input
        if not prompt_parts:
            prompt_parts = [""]

        for i, part in enumerate(prompt_parts):
            with tag.div(classes="flex gap-2"):
                with tag.input(
                    type="text",
                    name=f"prompt_part_{i}",
                    placeholder="Enter part of the prompt",
                    value=part.strip(),
                    classes=input_primary(),
                ):
                    pass
                if prompt_parts and i < len(prompt_parts):
                    with tag.button(
                        type="button",
                        # classes=button_danger(),
                        onclick="this.parentElement.remove()",
                    ):
                        text("×")

        with tag.button(
            type="button",
            classes=[button_secondary()],
            onclick="const container = document.getElementById('prompt-inputs'); const newDiv = document.createElement('div'); newDiv.className = 'flex gap-2 w-full'; newDiv.innerHTML = `<input type='text' name='prompt_part_${container.children.length}' placeholder='Enter part of the prompt' class='flex-1 border p-2 bg-white'><button type='button' class='bg-red-500 text-white px-3 py-2' onclick='this.parentElement.remove()'>×</button>`; container.appendChild(newDiv);",
        ):
            text("Add prompt part")

        with tag.button(
            type="submit",
            classes=[button_primary()],
        ):
            text("Generate")


def render_generation_options():
    with tag.div(classes="flex flex-col gap-4 py-2 px-4"):
        # Model selection
        with tag.div(classes="flex flex-col gap-1"):
            with tag.label(classes="text-sm font-medium"):
                text("Model")
            with tag.div(classes="flex flex-wrap gap-4"):
                for model_name, model_id in MODELS.items():
                    with tag.label(classes="flex items-center gap-2 text-xs"):
                        with tag.input(
                            type="radio",
                            name="model",
                            value=model_id,
                            checked=(model_id == MODELS["Flux 1.1 Pro Ultra"]),
                            classes="w-4 h-4",
                        ):
                            pass
                        text(model_name)

        # Aspect ratio selection
        with tag.div(classes="flex flex-col gap-1"):
            with tag.label(classes="text-sm font-medium"):
                text("Aspect Ratio")
            with tag.div(classes="flex flex-wrap gap-4"):
                for ratio in ASPECT_TO_RECRAFT.keys():
                    with tag.label(classes="flex items-center gap-2 text-xs"):
                        with tag.input(
                            type="radio",
                            name="aspect_ratio",
                            value=ratio,
                            checked=(ratio == "1:1"),
                            classes="w-4 h-4",
                        ):
                            pass
                        text(ratio)

        # Style selection
        with tag.div(classes="flex flex-col gap-1"):
            with tag.label(classes="text-sm font-medium"):
                text("Style")
            with tag.div(classes="flex gap-4"):
                for style in ["natural", "studio", "illustration", "flash"]:
                    with tag.label(classes="flex items-center gap-2 text-xs"):
                        with tag.input(
                            type="radio",
                            name="style",
                            value=style,
                            checked=(style == "natural"),
                            classes="w-4 h-4",
                        ):
                            pass
                        text(style.capitalize())


def render_prompt_modification_form():
    with tag.form(
        hx_post="/modify-prompt",
        hx_target="#prompt-container",
        hx_include="[name^='prompt_part_']",
        hx_swap="outerHTML",
        classes="flex flex-col gap-2  p-2",
    ):
        with tag.textarea(
            type="text",
            name="modification",
            placeholder="How to modify the prompt (e.g., 'make it more detailed')",
            classes=input_primary(),
            rows="4",
        ):
            pass

        with tag.button(
            type="submit",
            classes=button_primary(),
        ):
            text("Modify")


def render_prompt_form(prompt: str = None):
    """Render the prompt form with generation options and modification form."""
    with tag.div(
        id="prompt-container",
        classes="flex flex-col gap-4 p-2 bg-neutral-200 border-1 border-neutral-500 shadow-xl",
    ):
        # Main generation form
        with tag.form(
            hx_post="/generate",
            hx_target="#gallery-container",
            hx_swap="afterbegin settle:0.5s",
            hx_disabled_elt="input, button, select",
            classes="flex flex-col gap-4 w-full",
        ):
            render_generation_options()
            render_prompt_inputs(prompt)
        render_prompt_modification_form()


def add_external_scripts():
    with tag.script(src="https://unpkg.com/@tailwindcss/browser@4"):
        pass
    with tag.script(src="https://unpkg.com/htmx.org@2.0.4"):
        pass


@contextmanager
def render_base_layout():
    with tag.html(lang="en"):
        with tag.head():
            with tag.title():
                text("Yap")
            add_external_scripts()
        with tag.body(classes="bg-neutral-400 flex gap-4 h-screen"):
            yield
