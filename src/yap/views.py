import os

from tagflow import attr, classes, tag, text

from yap.base import (
    ASPECT_TO_RECRAFT,
    MODELS,
)


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


def render_prompt_pills(prompt, uuid_str):
    with tag.div(classes=flex_col()):
        classes("bg-neutral-300")
        with tag.div(classes=f"{flex_row()} max-w-xl justify-stretch"):
            with tag.button(
                type="button",
                classes=f"{button_primary()} flex-1",
                hx_post=f"/copy-prompt/{uuid_str}",
                hx_target="#prompt-container",
                hx_swap="outerHTML",
            ):
                text("Use prompt")
        with tag.ul(
            classes=[
                "px-2 text-xs flex flex-row flex-wrap gap-x-2 gap-y-2 flex-1 max-w-96 py-2 text-left justify-start",
                "border-l border-neutral-500 border-r border-b content-start",
            ]
        ):
            for part in prompt.split(","):
                part = part.strip()
                if part:
                    with tag.li():
                        with tag.button(
                            type="button",
                            classes=f"{button_secondary()} text-left",
                            hx_post="/add-prompt-part",
                            hx_target="#prompt-container",
                            hx_swap="outerHTML",
                            name="text",
                            value=part,
                            hx_include="[name^='prompt_part_']",
                        ):
                            text(part)


def render_image_or_status(prompt, filepath, status, uuid_str):
    if status == "complete" and filepath:
        with tag.img(
            src=f"/images/{os.path.basename(filepath)}",
            alt=prompt,
            classes="max-w-256 max-h-256 object-contain flex-0 bg-white p-2 shadow-xl shadow-neutral-500 z-10 border border-neutral-500 border-r-0",
        ):
            pass
    else:
        if status == "pending":
            attr("hx-get", f"/check/{uuid_str}")
            attr("hx-trigger", "load delay:1s")
            attr("hx-swap", "outerHTML")
        with tag.div(
            classes="bg-neutral-300 flex items-center justify-center p-2",
        ):
            with tag.span(classes="text-gray-500"):
                text("Generating..." if status == "pending" else "Error")


def render_single_image(prompt: str, filepath: str | None, status: str, uuid_str: str):
    """Render a single image card with appropriate HTMX attributes."""
    with tag.div(
        classes="flex p-2",
        id=f"generation-{uuid_str}",
    ):
        render_image_or_status(prompt, filepath, status, uuid_str)
        render_prompt_pills(prompt, uuid_str)


def generate_gallery(rows, current_page: int, total_pages: int):
    """Generate the HTML for the image gallery."""
    with tag.div(
        id="image-container",
        classes="h-full overflow-y-auto flex-1 flex flex-row flex-wrap py-4 content-start items-start justify-center",
    ):
        # Images
        for row in rows:
            prompt, filepath, status, uuid_str = row
            render_single_image(prompt, filepath, status, uuid_str)

        # Pagination controls
        if total_pages > 1:
            with tag.div(classes="flex justify-center items-center gap-4 mt-8"):
                # Previous page button
                if current_page > 1:
                    with tag.button(
                        hx_get=f"/gallery?page={current_page - 1}",
                        hx_target="#image-container",
                        classes="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded",
                    ):
                        text("Previous")

                # Page indicator
                with tag.span(classes="text-gray-600"):
                    text(f"Page {current_page} of {total_pages}")

                # Next page button
                if current_page < total_pages:
                    with tag.button(
                        hx_get=f"/gallery?page={current_page + 1}",
                        hx_target="#image-container",
                        classes="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded",
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
            hx_target="#image-container",
            hx_swap="afterbegin settle:0.5s",
            hx_disabled_elt="input, button, select",
            classes="flex flex-col gap-4 w-full",
        ):
            render_generation_options()
            render_prompt_inputs(prompt)
        render_prompt_modification_form()
