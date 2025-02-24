import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
import base64
import email
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from slopbox.gmail.model import Email, EmailAttachment

# If modifying these scopes, delete the token.pickle file.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_credentials() -> Optional[Credentials]:
    """Get valid user credentials from storage.

    The file token.pickle stores the user's access and refresh tokens, and is
    created automatically when the authorization flow completes for the first time.
    """
    creds = None
    token_path = os.path.expanduser("~/slopbox/token.pickle")
    credentials_path = os.path.expanduser("~/slopbox/credentials.json")

    # Load existing credentials if they exist
    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                return None
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    return creds


def parse_email_date(date_str: str) -> datetime:
    """Parse email date string into datetime object."""
    # Convert to seconds since epoch
    return datetime.fromtimestamp(int(date_str) / 1000.0)


def get_email_body(message_parts: dict) -> Tuple[Optional[str], Optional[str]]:
    """Extract email body (both plain text and HTML) from message parts."""
    body_text = None
    body_html = None

    if "parts" in message_parts:
        for part in message_parts["parts"]:
            if part["mimeType"] == "text/plain":
                body_text = base64.urlsafe_b64decode(part["body"]["data"]).decode(
                    "utf-8"
                )
            elif part["mimeType"] == "text/html":
                body_html = base64.urlsafe_b64decode(part["body"]["data"]).decode(
                    "utf-8"
                )
    elif "body" in message_parts and "data" in message_parts["body"]:
        if message_parts["mimeType"] == "text/plain":
            body_text = base64.urlsafe_b64decode(message_parts["body"]["data"]).decode(
                "utf-8"
            )
        elif message_parts["mimeType"] == "text/html":
            body_html = base64.urlsafe_b64decode(message_parts["body"]["data"]).decode(
                "utf-8"
            )

    return body_text, body_html


def sync_emails(max_results: int = 100) -> List[Email]:
    """Sync emails from Gmail to local database."""
    creds = get_credentials()
    if not creds:
        raise Exception("No valid credentials found. Please set up credentials.json")

    try:
        # Build the Gmail API service
        service = build("gmail", "v1", credentials=creds)

        # Get messages from Gmail
        results = (
            service.users()
            .messages()
            .list(userId="me", maxResults=max_results)
            .execute()
        )
        messages = results.get("messages", [])

        synced_emails = []
        for message in messages:
            # Get the full message details
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=message["id"], format="full")
                .execute()
            )

            # Extract headers
            headers = msg["payload"]["headers"]
            subject = next(
                (h["value"] for h in headers if h["name"].lower() == "subject"),
                "(no subject)",
            )
            sender = next(
                (h["value"] for h in headers if h["name"].lower() == "from"), "unknown"
            )
            recipient = next(
                (h["value"] for h in headers if h["name"].lower() == "to"), "unknown"
            )

            # Parse date
            date = parse_email_date(msg["internalDate"])

            # Get message body
            body_text, body_html = get_email_body(msg["payload"])

            # Create or update email in database
            email = Email.create_or_update(
                message_id=msg["id"],
                thread_id=msg["threadId"],
                subject=subject,
                sender=sender,
                recipient=recipient,
                date=date,
                snippet=msg["snippet"],
                body_text=body_text,
                body_html=body_html,
                labels=msg["labelIds"],
            )
            synced_emails.append(email)

            # Handle attachments if any
            if "parts" in msg["payload"]:
                for part in msg["payload"]["parts"]:
                    if "filename" in part and part["filename"]:
                        attachment = EmailAttachment.create(
                            email_id=email.id,
                            filename=part["filename"],
                            content_type=part["mimeType"],
                            size=int(part["body"].get("size", 0)),
                        )

        return synced_emails

    except HttpError as error:
        print(f"An error occurred: {error}")
        return []
