from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
import json

from slopbox.base import conn


@dataclass
class Email:
    id: int
    message_id: str
    thread_id: str
    subject: str
    sender: str
    recipient: str
    date: datetime
    snippet: str
    body_text: Optional[str]
    body_html: Optional[str]
    labels: List[str]
    created: datetime
    last_updated: datetime

    @classmethod
    def from_row(cls, row: tuple) -> "Email":
        return cls(
            id=row[0],
            message_id=row[1],
            thread_id=row[2],
            subject=row[3],
            sender=row[4],
            recipient=row[5],
            date=datetime.fromisoformat(row[6]),
            snippet=row[7],
            body_text=row[8],
            body_html=row[9],
            labels=json.loads(row[10]) if row[10] else [],
            created=datetime.fromisoformat(row[11]),
            last_updated=datetime.fromisoformat(row[12]),
        )

    @classmethod
    def create_or_update(
        cls,
        message_id: str,
        thread_id: str,
        subject: str,
        sender: str,
        recipient: str,
        date: datetime,
        snippet: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> "Email":
        """Create a new email record or update an existing one."""
        with conn:
            # Check for existing email
            cur = conn.execute(
                """
                SELECT id, message_id, thread_id, subject, sender, recipient,
                       date, snippet, body_text, body_html, labels, created,
                       last_updated
                FROM emails
                WHERE message_id = ?
                """,
                (message_id,),
            )
            row = cur.fetchone()

            labels_json = json.dumps(labels) if labels else None

            if row:
                # Update existing email
                cur = conn.execute(
                    """
                    UPDATE emails
                    SET thread_id = ?, subject = ?, sender = ?, recipient = ?,
                        date = ?, snippet = ?, body_text = ?, body_html = ?,
                        labels = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE message_id = ?
                    RETURNING id, message_id, thread_id, subject, sender,
                             recipient, date, snippet, body_text, body_html,
                             labels, created, last_updated
                    """,
                    (
                        thread_id,
                        subject,
                        sender,
                        recipient,
                        date.isoformat(),
                        snippet,
                        body_text,
                        body_html,
                        labels_json,
                        message_id,
                    ),
                )
            else:
                # Create new email
                cur = conn.execute(
                    """
                    INSERT INTO emails
                    (message_id, thread_id, subject, sender, recipient, date,
                     snippet, body_text, body_html, labels)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id, message_id, thread_id, subject, sender,
                             recipient, date, snippet, body_text, body_html,
                             labels, created, last_updated
                    """,
                    (
                        message_id,
                        thread_id,
                        subject,
                        sender,
                        recipient,
                        date.isoformat(),
                        snippet,
                        body_text,
                        body_html,
                        labels_json,
                    ),
                )

            return cls.from_row(cur.fetchone())


@dataclass
class EmailAttachment:
    id: int
    email_id: int
    filename: str
    content_type: str
    size: int
    filepath: Optional[str]
    created: datetime

    @classmethod
    def from_row(cls, row: tuple) -> "EmailAttachment":
        return cls(
            id=row[0],
            email_id=row[1],
            filename=row[2],
            content_type=row[3],
            size=row[4],
            filepath=row[5],
            created=datetime.fromisoformat(row[6]),
        )

    @classmethod
    def create(
        cls,
        email_id: int,
        filename: str,
        content_type: str,
        size: int,
        filepath: Optional[str] = None,
    ) -> "EmailAttachment":
        """Create a new email attachment record."""
        with conn:
            cur = conn.execute(
                """
                INSERT INTO email_attachments
                (email_id, filename, content_type, size, filepath)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id, email_id, filename, content_type, size,
                         filepath, created
                """,
                (email_id, filename, content_type, size, filepath),
            )
            return cls.from_row(cur.fetchone())


def get_email_count() -> int:
    """Get the total count of emails in the database."""
    with conn:
        cur = conn.execute("SELECT COUNT(*) FROM emails")
        return cur.fetchone()[0]


def get_paginated_emails(page_size: int, offset: int) -> List[Email]:
    """Get a paginated list of emails ordered by date desc."""
    with conn:
        cur = conn.execute(
            """
            SELECT id, message_id, thread_id, subject, sender, recipient,
                   date, snippet, body_text, body_html, labels, created,
                   last_updated
            FROM emails
            ORDER BY date DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        )
        return [Email.from_row(row) for row in cur.fetchall()]


def get_paginated_threads(
    page_size: int, offset: int
) -> List[Tuple[Email, List[Email]]]:
    """Get a paginated list of threads with their emails.

    Returns a list of tuples where each tuple contains:
    - The latest email in the thread (as the thread representative)
    - A list of all emails in the thread, ordered by date
    """
    with conn:
        # First get the thread IDs for this page, ordered by the latest message in each thread
        cur = conn.execute(
            """
            WITH ThreadLatestDates AS (
                SELECT thread_id, MAX(date) as latest_date
                FROM emails
                GROUP BY thread_id
            )
            SELECT thread_id
            FROM ThreadLatestDates
            ORDER BY latest_date DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        )
        thread_ids = [row[0] for row in cur.fetchall()]

        if not thread_ids:
            return []

        # Then get all emails for these threads
        placeholders = ",".join("?" * len(thread_ids))
        cur = conn.execute(
            f"""
            SELECT id, message_id, thread_id, subject, sender, recipient,
                   date, snippet, body_text, body_html, labels, created,
                   last_updated
            FROM emails
            WHERE thread_id IN ({placeholders})
            ORDER BY date DESC, thread_id DESC
            """,
            thread_ids,
        )

        # Group emails by thread
        threads = []
        current_thread = None
        current_emails = []

        for row in cur.fetchall():
            email = Email.from_row(row)

            if current_thread is None or email.thread_id != current_thread:
                if current_thread is not None:
                    threads.append((current_emails[0], current_emails))
                current_thread = email.thread_id
                current_emails = [email]
            else:
                current_emails.append(email)

        # Add the last thread
        if current_emails:
            threads.append((current_emails[0], current_emails))

        return threads


def get_thread_count() -> int:
    """Get the total count of unique threads in the database."""
    with conn:
        cur = conn.execute("SELECT COUNT(DISTINCT thread_id) FROM emails")
        return cur.fetchone()[0]


def get_thread_by_id(thread_id: str) -> List[Email]:
    """Get all emails in a specific thread, ordered by date desc."""
    with conn:
        cur = conn.execute(
            """
            SELECT id, message_id, thread_id, subject, sender, recipient,
                   date, snippet, body_text, body_html, labels, created,
                   last_updated
            FROM emails
            WHERE thread_id = ?
            ORDER BY date DESC
            """,
            (thread_id,),
        )
        return [Email.from_row(row) for row in cur.fetchall()]


def get_email_by_message_id(message_id: str) -> Optional[Email]:
    """Get a specific email by its message ID."""
    with conn:
        cur = conn.execute(
            """
            SELECT id, message_id, thread_id, subject, sender, recipient,
                   date, snippet, body_text, body_html, labels, created,
                   last_updated
            FROM emails
            WHERE message_id = ?
            """,
            (message_id,),
        )
        row = cur.fetchone()
        return Email.from_row(row) if row else None


def get_email_attachments(email_id: int) -> List[EmailAttachment]:
    """Get all attachments for a specific email."""
    with conn:
        cur = conn.execute(
            """
            SELECT id, email_id, filename, content_type, size, filepath, created
            FROM email_attachments
            WHERE email_id = ?
            ORDER BY created ASC
            """,
            (email_id,),
        )
        return [EmailAttachment.from_row(row) for row in cur.fetchall()]
