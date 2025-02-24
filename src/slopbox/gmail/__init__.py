from slopbox.gmail.model import (
    Email,
    EmailAttachment,
    get_email_attachments,
    get_email_by_message_id,
    get_email_count,
    get_paginated_emails,
)
from slopbox.gmail.routes import gmail_inbox, gmail_sync, gmail_thread_detail
from slopbox.gmail.sync import sync_emails
from slopbox.gmail.ui import render_page, render_thread_detail, render_thread_list

__all__ = [
    # Model classes and functions
    "Email",
    "EmailAttachment",
    "get_email_count",
    "get_paginated_emails",
    "get_email_by_message_id",
    "get_email_attachments",
    # Routes
    "gmail_inbox",
    "gmail_sync",
    "gmail_thread_detail",
    # Sync functions
    "sync_emails",
    # UI functions
    "render_page",
    "render_thread_list",
    "render_thread_detail",
]
