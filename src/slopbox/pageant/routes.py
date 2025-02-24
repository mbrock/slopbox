from fastapi import Request
from tagflow import tag, text

from slopbox.base import conn
from slopbox.ui import render_base_layout
from slopbox.pageant import model, ui


async def pageant():
    """Show the pageant page with a random pair of images."""
    # Initialize tables if they don't exist
    model.initialize_tables()

    # Get a random pair of images
    left_image, right_image = model.get_random_pair_for_comparison()
    if not left_image or not right_image:
        with render_base_layout():
            with tag.div("flex items-center justify-center min-h-screen"):
                with tag.p("text-lg text-neutral-600"):
                    text("Not enough images available for comparison.")
        return

    # Get current rankings
    rankings = model.get_top_rated_images()
    rankings_with_counts = []
    for image, rating in rankings:
        num_comparisons = model.get_comparison_count(image.uuid)
        rankings_with_counts.append((image, rating, num_comparisons))

    with render_base_layout():
        ui.render_page(left_image, right_image, rankings_with_counts)


async def pageant_choose(winner_uuid: str, loser_uuid: str):
    """Record a comparison result and return a new pair of images."""
    # Record the comparison
    model.record_comparison(winner_uuid, loser_uuid)

    # Get a new random pair
    left_image, right_image = model.get_random_pair_for_comparison()
    if not left_image or not right_image:
        with tag.div("flex items-center justify-center min-h-screen"):
            with tag.p("text-lg text-neutral-600"):
                text("No more images available for comparison.")
        return

    # Get updated rankings
    rankings = model.get_top_rated_images()
    rankings_with_counts = []
    for image, rating in rankings:
        num_comparisons = model.get_comparison_count(image.uuid)
        rankings_with_counts.append((image, rating, num_comparisons))

    ui.render_page(left_image, right_image, rankings_with_counts)
