import anthropic
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from slopbox.gmail.model import Email

# Initialize Claude client
claude = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


@dataclass
class EmailInsight:
    counterparty: str
    thread_ids: List[str]
    obligations: List[str]
    key_points: List[str]
    language: str
    due_date: Optional[datetime]
    priority: int  # 1-5, where 5 is highest
    category: str  # e.g., "Action Required", "FYI", "Follow-up"
    summary: str


async def analyze_emails(emails: List[Email]) -> List[EmailInsight]:
    """Analyze multiple emails in a single Claude prompt."""
    # Prepare the content for analysis
    email_contents = []
    for email in emails:
        email_contents.append(
            f"""
Email {len(email_contents) + 1}:
Subject: {email.subject}
From: {email.sender}
Date: {email.date}
Content: {email.body_text or email.body_html or email.snippet}
---"""
        )

    content = "\n".join(email_contents)

    message = await claude.messages.create(
        max_tokens=4096,  # Increased for multiple emails
        model="claude-3-5-sonnet-latest",
        system="""You are an expert at analyzing emails and extracting structured information.""",
        messages=[
            {
                "role": "user",
                "content": f"Please analyze these emails and extract structured information:\n\n{content}",
            }
        ],
        tools=[
            {
                "name": "presentEmailAnalysis",
                "description": "Present all important information about the emails in a structured format",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "cards": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "counterparty": {"type": "string"},
                                    "threadIds": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "obligations": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "key_points": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "language": {"type": "string"},
                                    "due_date": {
                                        "type": "string",
                                        "format": "date-time",
                                        "nullable": True,
                                    },
                                    "priority": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": 5,
                                    },
                                    "category": {
                                        "type": "string",
                                        "enum": ["Action Required", "Follow-up", "FYI"],
                                    },
                                    "summary": {"type": "string"},
                                },
                                "required": [
                                    "counterparty",
                                    "threadIds",
                                    "obligations",
                                    "key_points",
                                    "language",
                                    "priority",
                                    "category",
                                    "summary",
                                ],
                            },
                        }
                    },
                    "required": ["cards"],
                },
            }
        ],
    )

    # Extract the analysis from Claude's response
    analysis = None
    for content in message.content:
        if content.type == "tool_use" and content.name == "presentEmailAnalysis":
            analysis = content.input
            break

    if not analysis:
        raise ValueError("Failed to get analysis from Claude")

    insights = []
    for card in analysis["cards"]:
        # Convert the due date string to datetime if present
        due_date = None
        if card.get("due_date"):
            try:
                due_date = datetime.fromisoformat(card["due_date"])
            except ValueError:
                pass

        insights.append(
            EmailInsight(
                counterparty=card["counterparty"],
                thread_ids=card["threadIds"],
                obligations=card["obligations"],
                key_points=card["key_points"],
                language=card["language"],
                due_date=due_date,
                priority=card["priority"],
                category=card["category"],
                summary=card["summary"],
            )
        )

    return insights


async def analyze_thread(emails: List[Email]) -> List[EmailInsight]:
    """Analyze all emails in a thread."""
    insights = []
    for email in emails:
        insight = await analyze_emails([email])
        insights.append(insight[0])
    return insights
