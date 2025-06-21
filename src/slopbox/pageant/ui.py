from typing import List, Tuple

from tagflow import tag, text

from slopbox.image.img import get_image_url
from slopbox.model import Image


def render_comparison(left_image: Image, right_image: Image):
    """Render the side-by-side image comparison view for pageant."""
    with tag.div(
        "flex flex-col items-center justify-center min-h-screen"
        " bg-neutral-100 p-4",
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
        with tag.div(
            "flex gap-8 justify-center items-center w-full max-w-7xl mx-auto"
        ):
            # Left image container
            with tag.div("flex-1 flex justify-end"):
                with tag.div(
                    "group cursor-pointer transition-transform"
                    " hover:scale-105 relative",
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
                        src=get_image_url(left_image),
                        alt="Left image for comparison",
                    ):
                        pass

            # Right image container
            with tag.div("flex-1 flex justify-start"):
                with tag.div(
                    "group cursor-pointer transition-transform"
                    " hover:scale-105 relative",
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
                        src=get_image_url(right_image),
                        alt="Right image for comparison",
                    ):
                        pass


def render_rankings(rankings: List[Tuple[Image, float, int]]):
    """Render the current rankings table."""
    with tag.div(
        "mt-8 w-full max-w-2xl mx-auto bg-white rounded-lg shadow-lg p-6"
    ):
        with tag.h2("text-xl font-bold text-neutral-800 mb-4"):
            text("Current Rankings")
            with tag.span("text-sm font-normal text-neutral-600 ml-2"):
                text("(minimum 5 comparisons)")

        with tag.div("overflow-x-auto"):
            with tag.table("w-full"):
                with tag.thead("bg-neutral-100"):
                    with tag.tr():
                        with tag.th(
                            "px-4 py-2 text-left text-sm font-semibold"
                            " text-neutral-600"
                        ):
                            text("Rank")
                        with tag.th(
                            "px-4 py-2 text-left text-sm font-semibold"
                            " text-neutral-600"
                        ):
                            text("Image")
                        with tag.th(
                            "px-4 py-2 text-left text-sm font-semibold"
                            " text-neutral-600"
                        ):
                            text("Rating")
                        with tag.th(
                            "px-4 py-2 text-left text-sm font-semibold"
                            " text-neutral-600"
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
                                    src=get_image_url(image),
                                    alt=f"Rank {rank} image",
                                ):
                                    pass
                            with tag.td("px-4 py-2 text-sm text-neutral-600"):
                                text(f"{rating:.1f}")
                            with tag.td("px-4 py-2 text-sm text-neutral-600"):
                                text(str(num_comparisons))


def render_page(
    left_image: Image,
    right_image: Image,
    rankings: List[Tuple[Image, float, int]],
):
    """Render the complete pageant page with comparison and rankings."""
    with tag.div("flex flex-col mx-auto", id="pageant-container"):
        render_comparison(left_image, right_image)
        render_rankings(rankings)
