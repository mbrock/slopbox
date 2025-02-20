from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from yap.base import conn


@dataclass
class Image:
    id: int
    uuid: str
    prompt: str
    filepath: Optional[str]
    status: str
    model: str
    aspect_ratio: str
    created: datetime

    @classmethod
    def from_row(cls, row: tuple) -> "Image":
        return cls(
            id=row[0],
            uuid=row[1],
            prompt=row[2],
            filepath=row[3],
            status=row[4],
            model=row[5],
            aspect_ratio=row[6],
            created=datetime.fromisoformat(row[7]),
        )


def get_image_count() -> int:
    """Get the total count of images in the database."""
    with conn:
        cur = conn.execute("SELECT COUNT(*) FROM images_v2")
        return cur.fetchone()[0]


def get_paginated_images(
    page_size: int, offset: int
) -> List[Tuple[str, str, str, str]]:
    """Get a paginated list of images ordered by newest first."""
    with conn:
        cur = conn.execute(
            """
            SELECT prompt, filepath, status, uuid 
            FROM images_v2 
            ORDER BY id DESC 
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        )
        return cur.fetchall()


def create_pending_generation(
    generation_id: str, prompt: str, model: str, aspect_ratio: str
) -> None:
    """Create a new pending image generation record."""
    with conn:
        conn.execute(
            """
            INSERT INTO images_v2 
            (uuid, prompt, status, model, aspect_ratio) 
            VALUES (?, ?, ?, ?, ?)
            """,
            (generation_id, prompt, "pending", model, aspect_ratio),
        )


def get_generation_by_id(generation_id: str) -> Optional[Tuple[str, str, str, str]]:
    """Get a specific generation by its UUID."""
    with conn:
        cur = conn.execute(
            """
            SELECT prompt, filepath, status, uuid 
            FROM images_v2 
            WHERE uuid = ?
            """,
            (generation_id,),
        )
        return cur.fetchone()


def update_generation_status(
    generation_id: str, status: str, filepath: Optional[str] = None
) -> None:
    """Update the status and optionally the filepath of a generation."""
    if filepath:
        with conn:
            conn.execute(
                """
                UPDATE images_v2 
                SET status = ?, filepath = ? 
                WHERE uuid = ?
                """,
                (status, filepath, generation_id),
            )
    else:
        with conn:
            conn.execute(
                """
                UPDATE images_v2 
                SET status = ? 
                WHERE uuid = ?
                """,
                (status, generation_id),
            )


def get_prompt_by_uuid(uuid: str) -> Optional[str]:
    """Get the prompt for a specific image by UUID."""
    with conn:
        cur = conn.execute("SELECT prompt FROM images_v2 WHERE uuid = ?", (uuid,))
        row = cur.fetchone()
        return row[0] if row else None


def mark_stale_generations_as_error() -> None:
    """Update status of stale pending generations to error."""
    with conn:
        conn.execute(
            """
            UPDATE images_v2 
            SET status = 'error' 
            WHERE status = 'pending' 
            AND datetime(created, '+1 hour') < datetime('now')
            """
        )
