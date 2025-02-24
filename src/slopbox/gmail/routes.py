from typing import Optional
from fastapi import Query, Request
from tagflow import tag, text

from slopbox.gmail import model, sync, ui, ui_insights, claude_inbox
from slopbox.gmail.ui import format_date
from slopbox.ui import render_base_layout


def _handle_no_emails(message="No emails found."):
    """Render the no emails available message."""
    with render_base_layout():
        with tag.div("flex items-center justify-center min-h-screen"):
            with tag.p("text-lg text-neutral-600"):
                text(message)


async def gmail_insights(
    page: int = Query(1, ge=1),
    category: Optional[str] = None,
):
    """Show the Claude-powered smart inbox view."""
    # Get paginated threads
    threads = model.get_threads(page=page)
    if not threads:
        return _handle_no_emails()

    # Get total pages
    total_pages = model.get_total_pages()

    # Analyze threads with Claude
    insights = []
    for latest_email, _ in threads:
        insight = await claude_inbox.analyze_email(latest_email)
        insights.append(insight)

    # Filter by category if specified
    if category:
        filtered = [
            (t, i) for (t, i) in zip(threads, insights) if i.category == category
        ]
        if filtered:
            threads = [t for t, _ in filtered]
            insights = [i for _, i in filtered]
        else:
            return _handle_no_emails(f"No emails found in category: {category}")

    # Render the smart inbox view
    with render_base_layout():
        ui_insights.render_insight_list(threads, insights, page, total_pages)


async def gmail_inbox(request, page: int = 1):
    """Show the Gmail inbox page."""
    page_size = 25  # threads per page
    offset = (page - 1) * page_size

    # Get threads for this page
    threads = model.get_paginated_threads(page_size, offset)
    total_threads = model.get_thread_count()
    total_pages = max(1, (total_threads + page_size - 1) // page_size)

    if request.headers.get("HX-Request"):
        return ui.render_thread_list(threads, page, total_pages)

    with render_base_layout():
        ui.render_page(threads, page, total_pages)


async def gmail_sync():
    """Sync emails from Gmail."""
    try:
        synced_emails = sync.sync_emails()
        if not synced_emails:
            return _handle_no_emails("No new emails to sync.")

        # Return to first page after sync
        return await gmail_inbox(request=None, page=1)
    except Exception as e:
        return _handle_no_emails(f"Error syncing emails: {str(e)}")


async def gmail_thread_detail(thread_id: str):
    """Show the details of a specific thread."""
    emails = model.get_thread_by_id(thread_id)
    if not emails:
        return _handle_no_emails("Thread not found.")

    return ui.render_thread_detail(emails)


async def gmail_analyze(request: Request, page: int = 1):
    """Analyze all threads on the current page with Claude."""
    # Get threads for this page
    threads = model.get_paginated_threads(page_size=25, offset=(page - 1) * 25)
    if not threads:
        return _handle_no_emails()

    # Extract latest emails from threads for analysis
    latest_emails = [latest_email for latest_email, _ in threads]

    # Analyze all emails in one batch
    insights = await claude_inbox.analyze_emails(latest_emails)

    # Render the analyzed threads as cards
    with tag.div("grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"):
        for insight in insights:
            with tag.div(
                "bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition-shadow"
            ):
                # Header with badges
                with tag.div("flex items-center gap-2 mb-4"):
                    ui_insights.render_priority_badge(insight.priority)
                    ui_insights.render_category_badge(insight.category)
                    ui_insights.render_language_badge(insight.language)

                # Title and metadata
                with tag.div("mb-4"):
                    with tag.div("text-sm text-neutral-600"):
                        text(f"From: {insight.counterparty}")

                # Summary
                with tag.div("text-neutral-700 mb-4"):
                    text(insight.summary)

                # Action items
                if insight.obligations:
                    with tag.div("mb-4"):
                        with tag.h4("text-sm font-semibold text-neutral-700 mb-2"):
                            text("Action Items:")
                        with tag.ul("list-disc list-inside space-y-1"):
                            for obligation in insight.obligations:
                                with tag.li("text-neutral-600"):
                                    text(obligation)

                # Key points
                if insight.key_points:
                    with tag.div("mb-4"):
                        with tag.h4("text-sm font-semibold text-neutral-700 mb-2"):
                            text("Key Points:")
                        with tag.ul("list-disc list-inside space-y-1"):
                            for point in insight.key_points:
                                with tag.li("text-neutral-600"):
                                    text(point)

                # Due date
                if insight.due_date:
                    ui_insights.render_due_date(insight.due_date)

                # Link to thread
                with tag.div("mt-4 pt-4 border-t border-neutral-200"):
                    for thread_id in insight.thread_ids:
                        with tag.a(
                            "text-sm text-blue-600 hover:text-blue-800",
                            href=f"/gmail/thread/{thread_id}",
                            hx_get=f"/gmail/thread/{thread_id}",
                            hx_target="#email-detail",
                        ):
                            text("View Thread →")
