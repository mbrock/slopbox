import os

from tagflow import attr, tag, text

from slopbox.fastapi import app
from slopbox.model import Image


def get_image_url(image: Image) -> str:
    """
    Generate a URL for an image file.

    Args:
        image: The Image object containing the filepath

    Returns:
        The URL path to access the image

    Raises:
        AssertionError: If image.filepath is None
    """
    assert image.filepath is not None, "Image filepath cannot be None"
    return f"/images/{os.path.basename(image.filepath)}"


def get_image_container_classes(
    image, border_class="border border-neutral-500"
):
    """Get common styling classes for image containers."""
    base_classes = ["h-256", "z-10"]
    base_classes.append(border_class)

    aspect_style = f"aspect-{image.spec.aspect_ratio.replace(':', '/')}"
    base_classes.append(aspect_style)

    return base_classes


def render_image_or_status(image: Image):
    """Render just the image or its status indicator."""

    if image.status == "complete" and image.filepath:
        render_complete_image(image)
    elif image.status == "pending":
        render_pending_image(image)
    else:
        render_error_image(image)


def render_pending_image(image):
    classes = get_image_container_classes(image) + [
        "bg-white",
        "flex items-center justify-center",
    ]

    with tag.div(*classes):
        attr(
            "hx-get",
            app.url_path_for("check_status", generation_id=image.uuid),
        )
        attr("hx-trigger", "load delay:3s")
        attr("hx-swap", "outerHTML")
        with tag.span("text-gray-500"):
            text("Generating..." if image.status == "pending" else "Error")


def render_complete_image(image: Image):
    border_class = (
        "border-amber-200 border-4"
        if image.liked
        else "border border-neutral-500"
    )

    with tag.div("cursor-pointer relative group"):
        attr(
            "hx-post",
            app.url_path_for("toggle_like_endpoint", image_uuid=image.uuid),
        )
        attr("hx-target", f"#like-indicator-{image.uuid}")
        attr("hx-swap", "outerHTML")

        render_like_affordance(image)
        with tag.img(
            "object-contain flex-0",
            get_image_container_classes(image, border_class),
            src=get_image_url(image),
            alt=image.spec.prompt if image.spec else "",
        ):
            pass


def render_error_image(image):
    classes = get_image_container_classes(image, "border border-red-500") + [
        "bg-white",
        "flex items-center justify-center",
    ]

    with tag.div(*classes):
        with tag.span("text-red-500"):
            text("Error")


def render_like_affordance(image):
    with tag.div(
        "absolute top-2 right-2",
        "p-2 rounded-full",
        "opacity-0 group-hover:opacity-100 transition-opacity",
        "z-20 pointer-events-none",
        (
            "bg-amber-100 text-amber-600"
            if image.liked
            else "bg-white/80 text-neutral-600"
        ),
        id=f"like-indicator-{image.uuid}",
    ):
        with tag.span("text-xl"):
            text("♥")
