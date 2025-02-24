from slopbox.pageant.model import (
    initialize_tables,
    get_random_pair_for_comparison,
    record_comparison,
    get_top_rated_images,
    get_comparison_count,
)
from slopbox.pageant.routes import pageant, pageant_choose
from slopbox.pageant.ui import render_page, render_comparison, render_rankings

__all__ = [
    # Model functions
    "initialize_tables",
    "get_random_pair_for_comparison",
    "record_comparison",
    "get_top_rated_images",
    "get_comparison_count",
    # Routes
    "pageant",
    "pageant_choose",
    # UI functions
    "render_page",
    "render_comparison",
    "render_rankings",
]
