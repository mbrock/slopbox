from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from slopbox.base import conn
from slopbox.model import Image, ImageSpec


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


def initialize_tables():
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


def get_random_pair_for_comparison() -> Tuple[
    Optional[Image], Optional[Image]
]:
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
            Image.from_row(
                rows[0][:6], ImageSpec.from_row(rows[0][6:]), liked=True
            ),
            Image.from_row(
                rows[1][:6], ImageSpec.from_row(rows[1][6:]), liked=True
            ),
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

        expected_winner = 1.0 / (
            1.0 + 10 ** ((loser_rating - winner_rating) / 400.0)
        )
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
                Image.from_row(
                    row[:6], ImageSpec.from_row(row[6:11]), liked=True
                ),
                row[11],
            )
            for row in rows
        ]


def get_comparison_count(image_uuid: str) -> int:
    """Get the number of comparisons for an image."""
    with conn:
        cur = conn.execute(
            "SELECT num_comparisons FROM image_ratings WHERE image_uuid = ?",
            (image_uuid,),
        )
        row = cur.fetchone()
        return row[0] if row else 0
