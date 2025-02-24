from tagflow import tag, text

from slopbox.gmail import model, sync, ui
from slopbox.ui import render_base_layout


def _handle_no_emails(message="No emails found."):
    """Render the no emails available message."""
    with render_base_layout():
        with tag.div("flex items-center justify-center min-h-screen"):
            with tag.p("text-lg text-neutral-600"):
                text(message)


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
