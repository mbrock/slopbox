from contextlib import contextmanager
import os

from tagflow import tag, text


class Styles:
    button_primary = [
        "px-2 py-1",
        "text-sm font-semibold",
        "bg-slate-200 text-gray-800",
        "border-1 border-neutral-500",
        "shadow-sm",
        "hover:bg-slate-300",
        "disabled:opacity-50 disabled:cursor-not-allowed",
    ]

    button_secondary = [
        "px-2 py-1",
        "text-xs text-neutral-800",
        "bg-white bg-neutral-300",
        "ring-1 ring-inset ring-neutral-400",
        "hover:bg-neutral-100 hover:text-neutral-900",
    ]

    input_primary = [
        "flex-1 px-2",
        "text-sm",
        "bg-white",
        "border border-neutral-500",
        "placeholder:text-neutral-600 placeholder:italic",
        "field-sizing-content",
    ]

    spec_action_button = [
        "text-xs",
        "px-3 py-1",
        "bg-neutral-100 hover:bg-neutral-200",
        "border border-neutral-400",
    ]

    pagination_button = [
        "px-4",
        "bg-white hover:bg-neutral-100",
        "rounded shadow",
    ]

    pagination_text = ["text-neutral-700"]

    sort_button = [
        "px-3 py-1",
        "text-xs text-neutral-800",
        "bg-white",
        "ring-1 ring-inset ring-neutral-400",
        "hover:bg-neutral-100",
        "first:rounded-l last:rounded-r",
        "-ml-[1px]",  # Overlap borders
    ]

    sort_button_active = [
        *sort_button,
        "bg-neutral-300",
        "hover:bg-neutral-300",
        "relative",  # Ensure border shows on top
        "z-10",
    ]

    filter_button = [
        "px-3 py-1",
        "text-xs text-neutral-800",
        "bg-white",
        "rounded-full",
        "ring-1 ring-inset ring-neutral-400",
        "hover:bg-neutral-100",
        "flex items-center gap-1",
    ]

    filter_button_active = [
        *filter_button,
        "bg-amber-100",
        "hover:bg-amber-200",
        "ring-amber-400",
    ]

    radio_button = [
        "px-3 py-1.5",
        "text-xs text-neutral-800",
        "ring-1 ring-inset ring-neutral-400",
        "first:rounded-l last:rounded-r",
        "-ml-[1px]",
        "cursor-pointer",
        "group",
        "transition-colors",
        "flex-1",
    ]

    radio_button_inactive = [
        *radio_button,
        "bg-white",
        "hover:bg-neutral-200",
    ]

    radio_button_active = [
        *radio_button,
        "bg-neutral-300",
        "hover:bg-neutral-300",
        "relative",
        "z-10",
    ]


def render_radio_option(
    name: str,
    value: str,
    label: str,
    is_checked: bool = False,
):
    """Render a styled radio button option with label.

    Args:
        name: Name attribute for the radio group
        value: Value for this radio option
        label: Display label text
        is_checked: Whether this option is selected
    """
    with tag.div("flex items-center"):
        with tag.input(
            "relative size-4",
            "appearance-none rounded-full",
            "border border-neutral-300 bg-white",
            "before:absolute before:inset-1",
            "before:rounded-full before:bg-white",
            "checked:border-neutral-600 checked:bg-neutral-600",
            "focus-visible:outline focus-visible:outline-2",
            "focus-visible:outline-offset-2 focus-visible:outline-neutral-600",
            "[&:not(:checked)]:before:hidden",
            id=f"{name}-{value}",
            type="radio",
            name=name,
            value=value,
            checked=is_checked,
        ):
            pass
        with tag.label(
            "ml-3 text-sm font-medium text-neutral-900",
            for_=f"{name}-{value}",
        ):
            text(label)


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


def render_aspect_ratio_option(is_checked, ratio, scaled_width, scaled_height):
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


def render_pageant_comparison(left_image, right_image):
    """Render the side-by-side image comparison view for pageant."""
    with tag.div(
        "flex flex-col items-center justify-center min-h-screen bg-neutral-100 p-4",
    ):
        # Header
        with tag.div("mb-8 text-center"):
            with tag.h1("text-2xl font-bold text-neutral-800 mb-2"):
                text("Liked Images Pageant")
            with tag.p("text-neutral-600"):
                text("Click on the image you prefer (or press 1 or 2)!")
            with tag.p("text-sm text-neutral-500 mt-1"):
                text("(Only comparing images you've liked)")

        # Image comparison container
        with tag.div("flex gap-8 justify-center items-center w-full max-w-7xl mx-auto"):
            # Left image container
            with tag.div("flex-1 flex justify-end"):
                with tag.div(
                    "group cursor-pointer transition-transform hover:scale-105 relative",
                    hx_post=f"/pageant/choose/{left_image.uuid}/{right_image.uuid}",
                    hx_target="#pageant-container",
                    hx_swap="innerHTML",
                    hx_trigger="click, keyup[key=='1'] from:body",
                ):
                    # Number indicator
                    with tag.div(
                        "absolute -top-4 -left-4 w-8 h-8",
                        "bg-white rounded-full shadow-lg",
                        "flex items-center justify-center",
                        "text-lg font-bold text-neutral-600",
                        "border-2 border-neutral-200",
                    ):
                        text("1")
                    with tag.img(
                        "max-h-[70vh] rounded-lg shadow-lg",
                        "group-hover:ring-4 group-hover:ring-blue-400",
                        src=f"/images/{os.path.basename(left_image.filepath)}",
                        alt="Left image for comparison",
                    ):
                        pass

            # Right image container
            with tag.div("flex-1 flex justify-start"):
                with tag.div(
                    "group cursor-pointer transition-transform hover:scale-105 relative",
                    hx_post=f"/pageant/choose/{right_image.uuid}/{left_image.uuid}",
                    hx_target="#pageant-container",
                    hx_swap="innerHTML",
                    hx_trigger="click, keyup[key=='2'] from:body",
                ):
                    # Number indicator
                    with tag.div(
                        "absolute -top-4 -left-4 w-8 h-8",
                        "bg-white rounded-full shadow-lg",
                        "flex items-center justify-center",
                        "text-lg font-bold text-neutral-600",
                        "border-2 border-neutral-200",
                    ):
                        text("2")
                    with tag.img(
                        "max-h-[70vh] rounded-lg shadow-lg",
                        "group-hover:ring-4 group-hover:ring-blue-400",
                        src=f"/images/{os.path.basename(right_image.filepath)}",
                        alt="Right image for comparison",
                    ):
                        pass


def render_pageant_rankings(rankings):
    """Render the current rankings table."""
    with tag.div("mt-8 w-full max-w-2xl mx-auto bg-white rounded-lg shadow-lg p-6"):
        with tag.h2("text-xl font-bold text-neutral-800 mb-4"):
            text("Current Rankings")
            with tag.span("text-sm font-normal text-neutral-600 ml-2"):
                text("(minimum 5 comparisons)")

        with tag.div("overflow-x-auto"):
            with tag.table("w-full"):
                with tag.thead("bg-neutral-100"):
                    with tag.tr():
                        with tag.th(
                            "px-4 py-2 text-left text-sm font-semibold text-neutral-600"
                        ):
                            text("Rank")
                        with tag.th(
                            "px-4 py-2 text-left text-sm font-semibold text-neutral-600"
                        ):
                            text("Image")
                        with tag.th(
                            "px-4 py-2 text-left text-sm font-semibold text-neutral-600"
                        ):
                            text("Rating")
                        with tag.th(
                            "px-4 py-2 text-left text-sm font-semibold text-neutral-600"
                        ):
                            text("Comparisons")

                with tag.tbody():
                    for rank, (image, rating, num_comparisons) in enumerate(
                        rankings, 1
                    ):
                        with tag.tr("hover:bg-neutral-50"):
                            with tag.td("px-4 py-2 text-sm text-neutral-600"):
                                text(str(rank))
                            with tag.td("px-4 py-2"):
                                with tag.img(
                                    "h-16 rounded shadow",
                                    src=f"/images/{os.path.basename(image.filepath)}",
                                    alt=f"Rank {rank} image",
                                ):
                                    pass
                            with tag.td("px-4 py-2 text-sm text-neutral-600"):
                                text(f"{rating:.1f}")
                            with tag.td("px-4 py-2 text-sm text-neutral-600"):
                                text(str(num_comparisons))


def render_pageant_page(left_image, right_image, rankings):
    """Render the complete pageant page with comparison and rankings."""
    with tag.div("flex flex-col mx-auto", id="pageant-container"):
        render_pageant_comparison(left_image, right_image)
        render_pageant_rankings(rankings)
