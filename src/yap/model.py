from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from yap.base import conn


@dataclass
class ImageSpec:
    id: int
    prompt: str
    model: str
    aspect_ratio: str
    created: datetime

    @classmethod
    def from_row(cls, row: tuple) -> "ImageSpec":
        return cls(
            id=row[0],
            prompt=row[1],
            model=row[2],
            aspect_ratio=row[3],
            created=datetime.fromisoformat(row[4]),
        )

    @classmethod
    def create(cls, prompt: str, model: str, aspect_ratio: str) -> "ImageSpec":
        """Create a new image spec, or return an existing one with the same parameters."""
        with conn:
            # Check for existing spec
            cur = conn.execute(
                """
                SELECT id, prompt, model, aspect_ratio, created
                FROM image_specs
                WHERE prompt = ? AND model = ? AND aspect_ratio = ?
                """,
                (prompt, model, aspect_ratio),
            )
            row = cur.fetchone()
            if row:
                return cls.from_row(row)

            # Create new spec if none exists
            cur = conn.execute(
                """
                INSERT INTO image_specs (prompt, model, aspect_ratio)
                VALUES (?, ?, ?)
                RETURNING id, prompt, model, aspect_ratio, created
                """,
                (prompt, model, aspect_ratio),
            )
            return cls.from_row(cur.fetchone())


@dataclass
class Image:
    id: int
    uuid: str
    spec_id: int
    filepath: Optional[str]
    status: str
    created: datetime
    spec: Optional[ImageSpec] = None

    @classmethod
    def from_row(cls, row: tuple, spec: Optional[ImageSpec] = None) -> "Image":
        return cls(
            id=row[0],
            uuid=row[1],
            spec_id=row[2],
            filepath=row[3],
            status=row[4],
            created=datetime.fromisoformat(row[5]),
            spec=spec,
        )


def get_image_count() -> int:
    """Get the total count of images in the database."""
    with conn:
        cur = conn.execute("SELECT COUNT(*) FROM images_v3")
        return cur.fetchone()[0]


def get_paginated_images(page_size: int, offset: int) -> List[Image]:
    """Get a paginated list of images ordered by newest first."""
    with conn:
        cur = conn.execute(
            """
            SELECT 
                i.id, i.uuid, i.spec_id, i.filepath, i.status, i.created,
                s.id, s.prompt, s.model, s.aspect_ratio, s.created
            FROM images_v3 i
            JOIN image_specs s ON i.spec_id = s.id
            ORDER BY i.id DESC 
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        )
        rows = cur.fetchall()
        return [Image.from_row(row[:6], ImageSpec.from_row(row[6:])) for row in rows]


def create_pending_generation(
    generation_id: str, prompt: str, model: str, aspect_ratio: str
) -> None:
    """Create a new pending image generation record."""
    # First get or create the image spec
    spec = ImageSpec.create(prompt, model, aspect_ratio)

    # Then create the pending generation
    with conn:
        conn.execute(
            """
            INSERT INTO images_v3 
            (uuid, spec_id, status) 
            VALUES (?, ?, ?)
            """,
            (generation_id, spec.id, "pending"),
        )


def get_generation_by_id(generation_id: str) -> Optional[Image]:
    """Get a specific generation by its UUID."""
    with conn:
        cur = conn.execute(
            """
            SELECT 
                i.id, i.uuid, i.spec_id, i.filepath, i.status, i.created,
                s.id, s.prompt, s.model, s.aspect_ratio, s.created
            FROM images_v3 i
            JOIN image_specs s ON i.spec_id = s.id
            WHERE i.uuid = ?
            """,
            (generation_id,),
        )
        row = cur.fetchone()
        if row:
            return Image.from_row(row[:6], ImageSpec.from_row(row[6:]))
        return None


def update_generation_status(
    generation_id: str, status: str, filepath: Optional[str] = None
) -> None:
    """Update the status and optionally the filepath of a generation."""
    if filepath:
        with conn:
            conn.execute(
                """
                UPDATE images_v3 
                SET status = ?, filepath = ? 
                WHERE uuid = ?
                """,
                (status, filepath, generation_id),
            )
    else:
        with conn:
            conn.execute(
                """
                UPDATE images_v3 
                SET status = ? 
                WHERE uuid = ?
                """,
                (status, generation_id),
            )


def get_prompt_by_uuid(uuid: str) -> Optional[str]:
    """Get the prompt for a specific image by UUID."""
    with conn:
        cur = conn.execute(
            """
            SELECT s.prompt 
            FROM images_v3 i
            JOIN image_specs s ON i.spec_id = s.id
            WHERE i.uuid = ?
            """,
            (uuid,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def mark_stale_generations_as_error() -> None:
    """Update status of stale pending generations to error."""
    with conn:
        conn.execute(
            """
            UPDATE images_v3 
            SET status = 'error' 
            WHERE status = 'pending' 
            AND datetime(created, '+1 hour') < datetime('now')
            """
        )


def get_spec_generations(spec_id: int) -> List[Image]:
    """Get all generations for a specific image spec."""
    with conn:
        cur = conn.execute(
            """
            SELECT 
                i.id, i.uuid, i.spec_id, i.filepath, i.status, i.created,
                s.id, s.prompt, s.model, s.aspect_ratio, s.created
            FROM images_v3 i
            JOIN image_specs s ON i.spec_id = s.id
            WHERE i.spec_id = ?
            ORDER BY i.created DESC
            """,
            (spec_id,),
        )
        rows = cur.fetchall()
        return [Image.from_row(row[:6], ImageSpec.from_row(row[6:])) for row in rows]


def get_spec_count() -> int:
    """Get the total count of image specs in the database."""
    with conn:
        cur = conn.execute("SELECT COUNT(*) FROM image_specs")
        return cur.fetchone()[0]


def get_paginated_specs_with_images(
    page_size: int, offset: int
) -> List[Tuple[ImageSpec, List[Image]]]:
    """Get a paginated list of specs with their images, ordered by newest spec first."""
    with conn:
        # First get the paginated specs
        cur = conn.execute(
            """
            SELECT id, prompt, model, aspect_ratio, created
            FROM image_specs
            ORDER BY created DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        )
        specs = [ImageSpec.from_row(row) for row in cur.fetchall()]

        # Then for each spec, get its images
        result = []
        for spec in specs:
            cur = conn.execute(
                """
                SELECT 
                    i.id, i.uuid, i.spec_id, i.filepath, i.status, i.created
                FROM images_v3 i
                WHERE i.spec_id = ?
                ORDER BY i.created DESC
                """,
                (spec.id,),
            )
            images = [Image.from_row(row, spec) for row in cur.fetchall()]
            result.append((spec, images))

        return result
