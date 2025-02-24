from datetime import datetime
from typing import List, Optional, Tuple

from tagflow import tag, text

from slopbox.gmail.claude_inbox import EmailInsight
from slopbox.gmail.model import Email
from slopbox.ui import Styles


def render_priority_badge(priority: int):
    """Render a visual priority indicator."""
    colors = {
        5: "bg-red-100 text-red-800",
        4: "bg-orange-100 text-orange-800",
        3: "bg-yellow-100 text-yellow-800",
        2: "bg-blue-100 text-blue-800",
        1: "bg-green-100 text-green-800",
    }
    with tag.span(f"px-2 py-1 rounded-full text-xs font-medium {colors[priority]}"):
        text(f"P{priority}")


def render_category_badge(category: str):
    """Render a visual category indicator."""
    colors = {
        "Action Required": "bg-purple-100 text-purple-800",
        "Follow-up": "bg-blue-100 text-blue-800",
        "FYI": "bg-gray-100 text-gray-800",
    }
    with tag.span(f"px-2 py-1 rounded-full text-xs font-medium {colors[category]}"):
        text(category)


def render_language_badge(language: str):
    """Render a language indicator if not English."""
    if language.lower() != "english":
        with tag.span(
            "px-2 py-1 rounded-full text-xs font-medium bg-pink-100 text-pink-800"
        ):
            text(language)


def render_due_date(due_date: Optional[datetime]):
    """Render the due date with appropriate styling."""
    if not due_date:
        return

    # is_overdue = due_date < datetime.now()
    # color = "text-red-600" if is_overdue else "text-neutral-600"

    with tag.div("text-sm text-neutral-600"):
        with tag.span("mr-2"):
            text("Due:")
        text(due_date.strftime("%b %d, %Y"))


def render_insight_card(email: Email, insight: EmailInsight):
    """Render a card showing the email with Claude's insights."""
    with tag.div("bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition-shadow"):
        # Header section
        with tag.div("flex items-center justify-between mb-4"):
            # Left side - Priority and Category
            with tag.div("flex items-center gap-2"):
                render_priority_badge(insight.priority)
                render_category_badge(insight.category)
                render_language_badge(insight.language)

            # Right side - Due date if any
            render_due_date(insight.due_date)

        # Title and counterparty
        with tag.div("mb-4"):
            with tag.h3("text-lg font-semibold text-neutral-800 mb-1"):
                text(email.subject or "(no subject)")
            with tag.div("text-sm text-neutral-600"):
                text(f"From: {insight.counterparty}")

        # Summary
        with tag.div("text-neutral-700 mb-4"):
            text(insight.summary)

        # Obligations section
        if insight.obligations:
            with tag.div("mb-4"):
                with tag.h4("text-sm font-semibold text-neutral-700 mb-2"):
                    text("Action Items:")
                with tag.ul("list-disc list-inside space-y-1"):
                    for obligation in insight.obligations:
                        with tag.li("text-neutral-600"):
                            text(obligation)

        # Key points section
        if insight.key_points:
            with tag.div():
                with tag.h4("text-sm font-semibold text-neutral-700 mb-2"):
                    text("Key Points:")
                with tag.ul("list-disc list-inside space-y-1"):
                    for point in insight.key_points:
                        with tag.li("text-neutral-600"):
                            text(point)

        # Footer with original email link
        with tag.div("mt-4 pt-4 border-t border-neutral-200"):
            with tag.a(
                "text-sm text-blue-600 hover:text-blue-800",
                href=f"/gmail/thread/{email.thread_id}",
                hx_get=f"/gmail/thread/{email.thread_id}",
                hx_target="#email-detail",
            ):
                text("View Original Email →")


def render_insight_list(
    threads: List[Tuple[Email, List[Email]]],
    insights: List[EmailInsight],
    page: int,
    total_pages: int,
):
    """Render the insight-enhanced inbox view."""
    with tag.div("flex flex-col min-h-screen bg-neutral-100 p-4", id="email-insights"):
        # Header
        with tag.div("mb-8"):
            with tag.h1("text-2xl font-bold text-neutral-800 mb-2"):
                text("Smart Inbox")
            with tag.div("flex items-center gap-4"):
                # Sync button
                with tag.button(
                    *Styles.button_primary,
                    hx_post="/gmail/sync",
                    hx_target="#insight-container",
                ):
                    text("Sync Inbox")

                # Filter buttons
                with tag.div("flex items-center gap-2"):
                    for category in ["Action Required", "Follow-up", "FYI"]:
                        with tag.button(
                            *Styles.button_secondary,
                            hx_get=f"/gmail/insights?category={category}",
                            hx_target="#insight-container",
                        ):
                            text(category)

        # Insights container
        with tag.div("space-y-6", id="insight-container"):
            if not threads:
                with tag.div("p-8 text-center text-neutral-600"):
                    text("No emails found. Click 'Sync Inbox' to fetch your emails.")
                return

            for (email, _), insight in zip(threads, insights):
                render_insight_card(email, insight)

            # Pagination
            if total_pages > 1:
                with tag.div(
                    "flex items-center justify-between mt-6 bg-white rounded-lg shadow p-4"
                ):
                    # Previous page button
                    with tag.button(
                        *Styles.pagination_button,
                        hx_get=f"/gmail/insights?page={page - 1}",
                        hx_target="#email-insights",
                        hx_swap="outerHTML",
                        disabled=page <= 1,
                    ):
                        text("Previous")

                    # Page info
                    with tag.span(*Styles.pagination_text):
                        text(f"Page {page} of {total_pages}")

                    # Next page button
                    with tag.button(
                        *Styles.pagination_button,
                        hx_get=f"/gmail/insights?page={page + 1}",
                        hx_target="#email-insights",
                        hx_swap="outerHTML",
                        disabled=page >= total_pages,
                    ):
                        text("Next")
