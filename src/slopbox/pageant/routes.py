from tagflow import tag, text

from slopbox.pageant import model, ui
from slopbox.ui import render_base_layout


def _get_rankings():
    """Get current rankings with comparison counts."""
    rankings = model.get_top_rated_images()
    rankings_with_counts = []
    for image, rating in rankings:
        num_comparisons = model.get_comparison_count(image.uuid)
        rankings_with_counts.append((image, rating, num_comparisons))
    return rankings_with_counts


def _handle_no_images(message="Not enough images available for comparison."):
    """Render the no images available message."""
    with render_base_layout():
        with tag.div("flex items-center justify-center min-h-screen"):
            with tag.p("text-lg text-neutral-600"):
                text(message)


def _render_comparison_page(left_image, right_image):
    """Render the comparison page if images are available."""
    if not left_image or not right_image:
        return _handle_no_images()

    rankings_with_counts = _get_rankings()
    with render_base_layout():
        ui.render_page(left_image, right_image, rankings_with_counts)


async def pageant():
    """Show the pageant page with a random pair of images."""
    model.initialize_tables()
    left_image, right_image = model.get_random_pair_for_comparison()
    _render_comparison_page(left_image, right_image)


async def pageant_choose(winner_uuid: str, loser_uuid: str):
    """Record a comparison result and return a new pair of images."""
    model.record_comparison(winner_uuid, loser_uuid)
    left_image, right_image = model.get_random_pair_for_comparison()
    _render_comparison_page(left_image, right_image)
