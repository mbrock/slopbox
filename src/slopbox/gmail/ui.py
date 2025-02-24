import os
from datetime import datetime
from typing import List, Optional, Tuple

from tagflow import tag, text

from slopbox.gmail.model import Email, EmailAttachment, get_email_attachments
from slopbox.ui import Styles


def format_date(date: datetime) -> str:
    """Format a date for display."""
    return date.strftime("%b %d, %Y %I:%M %p")


def render_thread_list(
    threads: List[Tuple[Email, List[Email]]], page: int, total_pages: int
):
    """Render the thread list view."""
    with tag.div("flex flex-col min-h-screen bg-neutral-100 p-4", id="email-list"):
        # Header
        with tag.div("mb-8"):
            with tag.h1("text-2xl font-bold text-neutral-800 mb-2"):
                text("Gmail Inbox")
            with tag.div("flex items-center gap-4"):
                # Sync button
                with tag.button(
                    *Styles.button_primary,
                    hx_post="/gmail/sync",
                    hx_target="#email-container",
                ):
                    text("Sync Inbox")

                # Analyze with Claude button
                with tag.button(
                    *Styles.button_secondary,
                    hx_post=f"/gmail/analyze?page={page}",
                    hx_target="#email-container",
                    hx_swap="innerHTML",
                ):
                    text("Analyze with Claude")

        # Thread list container
        with tag.div("bg-white rounded-lg shadow-lg p-6", id="email-container"):
            if not threads:
                with tag.div("p-8 text-center text-neutral-600"):
                    text("No emails found. Click 'Sync Inbox' to fetch your emails.")
                return

            # Thread list
            with tag.div("divide-y divide-neutral-200"):
                for latest_email, thread_emails in threads:
                    with tag.div(
                        "p-4 hover:bg-neutral-50 cursor-pointer",
                        hx_get=f"/gmail/thread/{latest_email.thread_id}",
                        hx_target="#email-detail",
                    ):
                        with tag.div("flex items-center justify-between mb-1"):
                            with tag.div("flex items-center gap-2"):
                                with tag.div("font-medium text-neutral-800"):
                                    text(latest_email.sender)
                                with tag.div(
                                    "text-xs px-2 py-0.5 bg-neutral-100 rounded-full text-neutral-600"
                                ):
                                    text(f"{len(thread_emails)} messages")
                            with tag.div("text-sm text-neutral-500"):
                                text(format_date(latest_email.date))
                        with tag.div("text-neutral-800 truncate"):
                            text(latest_email.subject or "(no subject)")
                        with tag.div("text-sm text-neutral-600 truncate mt-1"):
                            text(latest_email.snippet)

            # Pagination
            if total_pages > 1:
                with tag.div("flex items-center justify-between mt-6"):
                    # Previous page button
                    with tag.button(
                        *Styles.pagination_button,
                        hx_get=f"/gmail?page={page - 1}",
                        hx_target="#email-list",
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
                        hx_get=f"/gmail?page={page + 1}",
                        hx_target="#email-list",
                        hx_swap="outerHTML",
                        disabled=page >= total_pages,
                    ):
                        text("Next")


def render_thread_detail(emails: List[Email]):
    """Render the detailed view of a thread."""
    with tag.div("bg-white rounded-lg shadow-lg p-6"):
        # Thread subject
        with tag.h2("text-xl font-bold text-neutral-800 mb-4"):
            text(emails[0].subject or "(no subject)")

        # Email list
        with tag.div("space-y-6"):
            for email in emails:
                with tag.div(
                    "border-t border-neutral-200 pt-4 first:border-0 first:pt-0"
                ):
                    # Email header
                    with tag.div("mb-4"):
                        with tag.div(
                            "flex items-center justify-between text-sm text-neutral-600"
                        ):
                            with tag.div():
                                text(f"From: {email.sender}")
                            with tag.div():
                                text(format_date(email.date))
                        with tag.div("text-sm text-neutral-600"):
                            text(f"To: {email.recipient}")

                    # Email body
                    with tag.div("prose max-w-none"):
                        if email.body_html:
                            # Use a sanitized version of the HTML content
                            with tag.div(
                                "mt-4",
                                _unsafe_html=email.body_html,
                            ):
                                pass
                        elif email.body_text:
                            with tag.pre(
                                "whitespace-pre-wrap font-sans text-neutral-800 mt-4"
                            ):
                                text(email.body_text)

                    # Attachments
                    attachments = get_email_attachments(email.id)
                    if attachments:
                        with tag.div("mt-4"):
                            with tag.div("text-sm font-semibold text-neutral-800 mb-2"):
                                text("Attachments")
                            with tag.div("space-y-2"):
                                for attachment in attachments:
                                    with tag.div(
                                        "flex items-center justify-between p-2 bg-neutral-50 rounded"
                                    ):
                                        with tag.div("flex items-center gap-2"):
                                            with tag.span("text-neutral-800"):
                                                text(attachment.filename)
                                            with tag.span("text-sm text-neutral-500"):
                                                text(f"({attachment.size} bytes)")
                                        if attachment.filepath:
                                            with tag.a(
                                                *Styles.button_secondary,
                                                href=f"/gmail/attachment/{attachment.id}",
                                                download=attachment.filename,
                                            ):
                                                text("Download")


def render_page(threads: List[Tuple[Email, List[Email]]], page: int, total_pages: int):
    """Render the complete email page with thread list and detail views."""
    with tag.div("flex flex-col min-h-screen bg-neutral-100 p-4", id="email-list"):
        # Thread list
        with tag.div():
            render_thread_list(threads, page, total_pages)

        # Thread detail container
        with tag.div(id="email-detail"):
            with tag.div(
                "flex items-center justify-center h-full text-neutral-600 italic"
            ):
                text("Select a thread to view its messages")
