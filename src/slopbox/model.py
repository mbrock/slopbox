from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
import re
import logging

from slopbox.base import conn

logger = logging.getLogger(__name__)


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
    liked: bool = False

    @classmethod
    def from_row(
        cls, row: tuple, spec: Optional[ImageSpec] = None, liked: bool = False
    ) -> "Image":
        return cls(
            id=row[0],
            uuid=row[1],
            spec_id=row[2],
            filepath=row[3],
            status=row[4],
            created=datetime.fromisoformat(row[5]),
            spec=spec,
            liked=liked,
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


def get_gallery_total_pages(liked_only: bool = False) -> int:
    """Get the total number of pages in the gallery based on distinct dates with content."""
    with conn:
        date_query = """
            SELECT COUNT(DISTINCT date(s.created))
            FROM image_specs s
            JOIN images_v3 i ON i.spec_id = s.id
            WHERE i.status = 'complete'
        """

        if liked_only:
            date_query = """
                SELECT COUNT(DISTINCT date(s.created))
                FROM image_specs s
                JOIN images_v3 i ON i.spec_id = s.id
                JOIN likes l ON i.uuid = l.image_uuid
                WHERE i.status = 'complete'
            """

        cur = conn.execute(date_query)
        total_pages = cur.fetchone()[0]
        return max(1, total_pages)  # Ensure at least 1 page


def get_paginated_specs_with_images(
    page_size: int,
    offset: int,
    sort_by: str = "recency",  # "recency" or "image_count"
    liked_only: bool = False,
) -> List[Tuple[ImageSpec, List[Image]]]:
    """Get a paginated list of specs with their images, grouped by date.

    Args:
        page_size: Number of dates to fetch
        offset: Number of dates with content to skip
        sort_by: How to sort specs within each date
        liked_only: Whether to only include specs with liked images
    """
    logger.info(
        f"Getting paginated specs with page_size={page_size}, offset={offset}, sort_by={sort_by}, liked_only={liked_only}"
    )

    with conn:
        # First get the dates that have content, applying pagination to the dates
        date_query = """
            WITH dates_with_content AS (
                SELECT DISTINCT date(s.created) as spec_date
                FROM image_specs s
                JOIN images_v3 i ON i.spec_id = s.id
                WHERE i.status = 'complete'
                {liked_filter}
                ORDER BY spec_date DESC
                LIMIT ? OFFSET ?
            )
            SELECT spec_date FROM dates_with_content
        """

        liked_filter = (
            "AND i.uuid IN (SELECT image_uuid FROM likes)" if liked_only else ""
        )

        # Get the target dates for this page
        cur = conn.execute(
            date_query.format(liked_filter=liked_filter), (page_size, offset)
        )
        target_dates = [row[0] for row in cur.fetchall()]

        if not target_dates:
            logger.info("No dates found, returning empty list")
            return []

        # Now get all specs for these dates
        spec_query = """
            WITH spec_counts AS (
                SELECT s.id,
                    (SELECT COUNT(*) FROM images_v3 WHERE spec_id = s.id AND status = 'complete') as image_count
                FROM image_specs s
            )
            SELECT DISTINCT s.*
            FROM image_specs s
            JOIN images_v3 i ON i.spec_id = s.id
            JOIN spec_counts sc ON s.id = sc.id
            WHERE i.status = 'complete'
            AND date(s.created) IN ({date_placeholders})
            {liked_filter}
            ORDER BY date(s.created) DESC, {sort_clause}
        """

        sort_clause = (
            "s.created DESC"
            if sort_by == "recency"
            else "sc.image_count DESC, s.created DESC"
        )

        date_placeholders = ",".join("?" * len(target_dates))
        spec_query = spec_query.format(
            date_placeholders=date_placeholders,
            liked_filter=liked_filter,
            sort_clause=sort_clause,
        )

        logger.info(f"Executing spec query for dates: {target_dates}")
        cur = conn.execute(spec_query, target_dates)
        specs = [ImageSpec.from_row(row) for row in cur.fetchall()]
        logger.info(f"Found {len(specs)} specs")

        # Get all complete images for these specs
        if not specs:
            logger.info("No specs found, returning empty list")
            return []

        image_query = """
            SELECT 
                i.id, i.uuid, i.spec_id, i.filepath, i.status, i.created,
                EXISTS(SELECT 1 FROM likes WHERE image_uuid = i.uuid) as liked
            FROM images_v3 i
            WHERE i.spec_id IN ({placeholders})
            AND i.status = 'complete'
            ORDER BY i.created DESC
        """
        placeholders = ",".join("?" * len(specs))
        spec_ids = [spec.id for spec in specs]
        specs_by_id = {spec.id: spec for spec in specs}

        logger.info(f"Executing image query for spec_ids: {spec_ids}")
        cur = conn.execute(image_query.format(placeholders=placeholders), spec_ids)

        # Group images by spec_id
        images_by_spec = {}
        for row in cur.fetchall():
            image = Image.from_row(row[:6], specs_by_id[row[2]], liked=row[6])
            if image.spec_id not in images_by_spec:
                images_by_spec[image.spec_id] = []
            images_by_spec[image.spec_id].append(image)

        logger.info(f"Found images for {len(images_by_spec)} specs")
        for spec_id, images in images_by_spec.items():
            logger.info(f"Spec {spec_id} has {len(images)} images")

        # Return specs with their images
        result = [(spec, images_by_spec.get(spec.id, [])) for spec in specs]
        logger.info(f"Returning {len(result)} spec-image pairs")
        return result


def split_prompt(prompt: str) -> List[str]:
    """
    Split a prompt into parts. The entire prompt is treated as either:
    - Sentence-based (if it contains any periods followed by space/newline) - in which case split only on sentence boundaries
    - Comma-based (if no sentence breaks are detected) - in which case split on commas
    Never modifies the content of the parts themselves.
    """
    # Clean up the prompt
    prompt = prompt.strip()

    # Check if we have any sentences (looking for period + space/newline)
    if re.search(r"\.(?:\s+|\n+)", prompt):
        # Split on sentence boundaries, keeping everything else intact
        parts = re.split(r"(?<=\.)(?:\s+|\n+)", prompt)
        return [p.strip() for p in parts if p.strip()]
    else:
        # No sentence structure detected, split on commas
        parts = [p.strip() for p in prompt.split(",") if p.strip()]
        return parts if parts else [prompt]


def get_random_weighted_image() -> Tuple[Optional[Image], Optional[int]]:
    """Get a random completed image with some weighting based on spec popularity.

    First randomly selects a spec (weighted by image count), then randomly selects
    an image from that spec. This provides better distribution across specs while
    still favoring successful ones.

    Returns:
        A tuple of (Image, image_count) where image_count is the number of completed images in the spec.
    """
    with conn:
        # First randomly select a spec, weighted by completed image count
        cur = conn.execute(
            """
            WITH spec_counts AS (
                SELECT spec_id, COUNT(*) as count
                FROM images_v3
                WHERE status = 'complete'
                GROUP BY spec_id
            )
            SELECT spec_id, count
            FROM spec_counts
            ORDER BY RANDOM() * SQRT(count)
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            return (None, None)

        spec_id, count = row

        # Then randomly select an image from that spec
        cur = conn.execute(
            """
            SELECT
                i.id, i.uuid, i.spec_id, i.filepath, i.status, i.created,
                s.id, s.prompt, s.model, s.aspect_ratio, s.created
            FROM images_v3 i
            JOIN image_specs s ON i.spec_id = s.id
            WHERE i.spec_id = ? AND i.status = 'complete'
            ORDER BY RANDOM()
            LIMIT 1
            """,
            (spec_id,),
        )
        row = cur.fetchone()
        if row:
            return (Image.from_row(row[:6], ImageSpec.from_row(row[6:])), count)
        return (None, None)


def get_random_spec_image(spec_id: int) -> Tuple[Optional[Image], Optional[int]]:
    """Get a random completed image from a specific spec.

    Returns:
        A tuple of (Image, image_count) where image_count is the number of completed images in the spec.
    """
    with conn:
        # Get the count of completed images for this spec
        cur = conn.execute(
            """
            SELECT COUNT(*)
            FROM images_v3
            WHERE spec_id = ? AND status = 'complete'
            """,
            (spec_id,),
        )
        count = cur.fetchone()[0]
        if count == 0:
            return (None, None)

        # Get a random completed image from this spec
        cur = conn.execute(
            """
            SELECT
                i.id, i.uuid, i.spec_id, i.filepath, i.status, i.created,
                s.id, s.prompt, s.model, s.aspect_ratio, s.created
            FROM images_v3 i
            JOIN image_specs s ON i.spec_id = s.id
            WHERE i.spec_id = ? AND i.status = 'complete'
            ORDER BY RANDOM()
            LIMIT 1
            """,
            (spec_id,),
        )
        row = cur.fetchone()
        if row:
            return (Image.from_row(row[:6], ImageSpec.from_row(row[6:])), count)
        return (None, None)


def toggle_like(image_uuid: str) -> bool:
    """Toggle like status for an image. Returns new like status."""
    with conn:
        # Check if image exists and is complete
        cur = conn.execute(
            "SELECT 1 FROM images_v3 WHERE uuid = ? AND status = 'complete'",
            (image_uuid,),
        )
        if not cur.fetchone():
            return False

        # Check current like status
        cur = conn.execute(
            "SELECT 1 FROM likes WHERE image_uuid = ?",
            (image_uuid,),
        )
        currently_liked = bool(cur.fetchone())

        if currently_liked:
            conn.execute(
                "DELETE FROM likes WHERE image_uuid = ?",
                (image_uuid,),
            )
            return False
        else:
            conn.execute(
                "INSERT INTO likes (image_uuid) VALUES (?)",
                (image_uuid,),
            )
            return True


def get_liked_status(image_uuids: List[str]) -> dict[str, bool]:
    """Get like status for multiple images at once."""
    if not image_uuids:
        return {}

    with conn:
        placeholders = ",".join("?" * len(image_uuids))
        cur = conn.execute(
            f"SELECT image_uuid FROM likes WHERE image_uuid IN ({placeholders})",
            image_uuids,
        )
        liked_uuids = {row[0] for row in cur.fetchall()}
        return {uuid: uuid in liked_uuids for uuid in image_uuids}


def get_random_liked_image() -> Tuple[Optional[Image], Optional[int]]:
    """Get a random liked image.

    Returns:
        A tuple of (Image, image_count) where image_count is the total number of liked images.
    """
    with conn:
        # Get the count of liked images
        cur = conn.execute(
            """
            SELECT COUNT(*)
            FROM images_v3 i
            JOIN likes l ON i.uuid = l.image_uuid
            WHERE i.status = 'complete'
            """
        )
        count = cur.fetchone()[0]
        if count == 0:
            return (None, None)

        # Get a random liked image
        cur = conn.execute(
            """
            SELECT
                i.id, i.uuid, i.spec_id, i.filepath, i.status, i.created,
                s.id, s.prompt, s.model, s.aspect_ratio, s.created
            FROM images_v3 i
            JOIN image_specs s ON i.spec_id = s.id
            JOIN likes l ON i.uuid = l.image_uuid
            WHERE i.status = 'complete'
            ORDER BY RANDOM()
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row:
            image = Image.from_row(row[:6], ImageSpec.from_row(row[6:]))
            image.liked = True  # Since we know it's liked
            return (image, count)
        return (None, None)


@dataclass
class ImageRating:
    image_uuid: str
    rating: float
    num_comparisons: int
    created: datetime
    updated: datetime

    @classmethod
    def from_row(cls, row: tuple) -> "ImageRating":
        return cls(
            image_uuid=row[0],
            rating=row[1],
            num_comparisons=row[2],
            created=datetime.fromisoformat(row[3]),
            updated=datetime.fromisoformat(row[4]),
        )


@dataclass
class ComparisonEvent:
    id: int
    winner_uuid: str
    loser_uuid: str
    created: datetime

    @classmethod
    def from_row(cls, row: tuple) -> "ComparisonEvent":
        return cls(
            id=row[0],
            winner_uuid=row[1],
            loser_uuid=row[2],
            created=datetime.fromisoformat(row[3]),
        )


def initialize_pageant_tables():
    """Create the necessary tables for the pageant feature if they don't exist."""
    with conn:
        # Table for storing ELO ratings
        conn.execute("""
            CREATE TABLE IF NOT EXISTS image_ratings (
                image_uuid TEXT PRIMARY KEY,
                rating REAL NOT NULL DEFAULT 1500.0,
                num_comparisons INTEGER NOT NULL DEFAULT 0,
                created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_uuid) REFERENCES images_v3 (uuid)
            )
        """)

        # Table for storing comparison events
        conn.execute("""
            CREATE TABLE IF NOT EXISTS comparison_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                winner_uuid TEXT NOT NULL,
                loser_uuid TEXT NOT NULL,
                created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (winner_uuid) REFERENCES images_v3 (uuid),
                FOREIGN KEY (loser_uuid) REFERENCES images_v3 (uuid)
            )
        """)


def get_random_pair_for_comparison() -> Tuple[Optional[Image], Optional[Image]]:
    """Get two random liked images for comparison that haven't been compared too many times."""
    with conn:
        # Get two random liked images, preferring those with fewer comparisons
        cur = conn.execute("""
            WITH RankedImages AS (
                SELECT 
                    i.uuid,
                    COALESCE(r.num_comparisons, 0) as comp_count
                FROM images_v3 i
                JOIN likes l ON i.uuid = l.image_uuid
                LEFT JOIN image_ratings r ON i.uuid = r.image_uuid
                WHERE i.status = 'complete'
                ORDER BY RANDOM() * (1.0 / (COALESCE(r.num_comparisons, 0) + 1))
                LIMIT 2
            )
            SELECT 
                i.id, i.uuid, i.spec_id, i.filepath, i.status, i.created,
                s.id, s.prompt, s.model, s.aspect_ratio, s.created
            FROM RankedImages r
            JOIN images_v3 i ON r.uuid = i.uuid
            JOIN image_specs s ON i.spec_id = s.id
        """)
        rows = cur.fetchall()
        if len(rows) < 2:
            return None, None
        return (
            Image.from_row(rows[0][:6], ImageSpec.from_row(rows[0][6:]), liked=True),
            Image.from_row(rows[1][:6], ImageSpec.from_row(rows[1][6:]), liked=True),
        )


def record_comparison(winner_uuid: str, loser_uuid: str) -> None:
    """Record a comparison result and update ELO ratings."""
    K = 32  # ELO K-factor

    with conn:
        # Get current ratings
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO image_ratings (image_uuid, rating)
            VALUES (?, 1500.0), (?, 1500.0)
        """,
            (winner_uuid, loser_uuid),
        )

        cur = conn.execute(
            """
            SELECT image_uuid, rating
            FROM image_ratings
            WHERE image_uuid IN (?, ?)
        """,
            (winner_uuid, loser_uuid),
        )
        ratings = dict(cur.fetchall())

        # Calculate new ELO ratings
        winner_rating = ratings[winner_uuid]
        loser_rating = ratings[loser_uuid]

        expected_winner = 1.0 / (1.0 + 10 ** ((loser_rating - winner_rating) / 400.0))
        expected_loser = 1.0 - expected_winner

        new_winner_rating = winner_rating + K * (1 - expected_winner)
        new_loser_rating = loser_rating + K * (0 - expected_loser)

        # Update ratings
        conn.execute(
            """
            UPDATE image_ratings
            SET rating = ?,
                num_comparisons = num_comparisons + 1,
                updated = CURRENT_TIMESTAMP
            WHERE image_uuid = ?
        """,
            (new_winner_rating, winner_uuid),
        )

        conn.execute(
            """
            UPDATE image_ratings
            SET rating = ?,
                num_comparisons = num_comparisons + 1,
                updated = CURRENT_TIMESTAMP
            WHERE image_uuid = ?
        """,
            (new_loser_rating, loser_uuid),
        )

        # Record comparison event
        conn.execute(
            """
            INSERT INTO comparison_events (winner_uuid, loser_uuid)
            VALUES (?, ?)
        """,
            (winner_uuid, loser_uuid),
        )


def get_top_rated_images(limit: int = 10) -> List[Tuple[Image, float]]:
    """Get the top rated liked images with their ratings."""
    with conn:
        cur = conn.execute(
            """
            SELECT 
                i.id, i.uuid, i.spec_id, i.filepath, i.status, i.created,
                s.id, s.prompt, s.model, s.aspect_ratio, s.created,
                r.rating
            FROM image_ratings r
            JOIN images_v3 i ON r.image_uuid = i.uuid
            JOIN image_specs s ON i.spec_id = s.id
            JOIN likes l ON i.uuid = l.image_uuid
            WHERE r.num_comparisons >= 5  -- Minimum number of comparisons to be ranked
            ORDER BY r.rating DESC
            LIMIT ?
        """,
            (limit,),
        )
        rows = cur.fetchall()
        return [
            (
                Image.from_row(row[:6], ImageSpec.from_row(row[6:11]), liked=True),
                row[11],
            )
            for row in rows
        ]
