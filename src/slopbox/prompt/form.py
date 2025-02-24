from tagflow import html, tag, text, attr

from slopbox.base import MODELS, DEFAULT_MODEL, ASPECT_TO_RECRAFT
from slopbox.fastapi import app
from slopbox.model import split_prompt
from slopbox.ui import Styles, render_radio_option, render_aspect_ratio_option


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

@html.div("flex flex-col gap-2")
def render_generation_options(model: str = None, aspect_ratio: str = None):
    # Model selection
    with tag.fieldset("flex flex-col gap-2"):
        with tag.span("text-xs text-neutral-600"):
            text("Model")
        with tag.div("flex gap-4"):
            for model_name, model_id in MODELS.items():
                is_checked = model_id == model if model else model_id == DEFAULT_MODEL
                render_radio_option("model", model_id, model_name, is_checked)

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

                render_aspect_ratio_option(
                    is_checked, ratio, scaled_width, scaled_height
                )


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
    ):
        pass

    with tag.button(
        Styles.button_primary,
        type="submit",
    ):
        text("Modify")


