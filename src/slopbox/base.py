import os
import sqlite3

MODELS = {
    "Flux Ultra": "black-forest-labs/flux-1.1-pro-ultra",
    "Flux Dev": "black-forest-labs/flux-dev",
    "Flux Schnell": "black-forest-labs/flux-schnell",
    "Recraft v3": "recraft-ai/recraft-v3",
}

DEFAULT_MODEL = MODELS["Flux Ultra"]

ASPECT_TO_RECRAFT = {
    "16:9": "1820x1024",  # Widescreen
    "4:3": "1365x1024",  # Standard
    "1:1": "1024x1024",  # Square
    "3:4": "1024x1365",  # Portrait standard
    "9:16": "1024x1820",  # Portrait
}

RECRAFT_SIZES = [
    "1024x1024",
    "1365x1024",
    "1024x1365",
    "1536x1024",
    "1024x1536",
    "1820x1024",
    "1024x1820",
    "1024x2048",
    "2048x1024",
    "1434x1024",
    "1024x1434",
    "1024x1280",
    "1280x1024",
    "1024x1707",
    "1707x1024",
]

IMAGE_DIR = os.path.expanduser("~/slopbox/img")
os.makedirs(IMAGE_DIR, exist_ok=True)

DB_PATH = os.path.expanduser("~/slopbox/img.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)


def create_tables():
    with conn:
        # Create image_specs table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS image_specs (
                id INTEGER PRIMARY KEY,
                prompt TEXT NOT NULL,
                model TEXT NOT NULL,
                aspect_ratio TEXT NOT NULL,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(prompt, model, aspect_ratio)
            )
            """
        )

        # Create new images table with spec_id reference
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS images_v3 (
                id INTEGER PRIMARY KEY,
                uuid TEXT UNIQUE,
                spec_id INTEGER NOT NULL,
                filepath TEXT,
                status TEXT DEFAULT 'pending',
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (spec_id) REFERENCES image_specs (id)
            )
            """
        )

        # Create likes table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS likes (
                image_uuid TEXT PRIMARY KEY,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_uuid) REFERENCES images_v3 (uuid)
            )
            """
        )

        # Create emails table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY,
                message_id TEXT UNIQUE NOT NULL,
                thread_id TEXT NOT NULL,
                subject TEXT,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                date TIMESTAMP NOT NULL,
                snippet TEXT,
                body_text TEXT,
                body_html TEXT,
                labels TEXT,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Create email attachments table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_attachments (
                id INTEGER PRIMARY KEY,
                email_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                filepath TEXT,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES emails (id)
            )
            """
        )


def migrate_v2_to_v3():
    """Migrate data from images_v2 to the new schema."""
    with conn:
        # Check if migration is needed
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='images_v2'"
        )
        if not cur.fetchone():
            return

        # Create new tables if they don't exist
        create_tables()

        # Insert specs with their earliest creation time
        conn.execute(
            """
            INSERT INTO image_specs (prompt, model, aspect_ratio, created)
            SELECT
                prompt,
                model,
                aspect_ratio,
                MIN(created) as first_created
            FROM images_v2
            GROUP BY prompt, model, aspect_ratio
            """
        )

        # Then insert images with the correct spec_ids
        conn.execute(
            """
            INSERT INTO images_v3 (uuid, spec_id, filepath, status, created)
            SELECT
                v2.uuid,
                s.id,
                v2.filepath,
                v2.status,
                v2.created
            FROM images_v2 v2
            JOIN image_specs s
                ON s.prompt = v2.prompt
                AND s.model = v2.model
                AND s.aspect_ratio = v2.aspect_ratio
            """
        )

        # Rename old table to backup
        conn.execute("ALTER TABLE images_v2 RENAME TO images_v2_backup")


def prompt_modification_system_message():
    return os.environ.get(
        "PROMPT_MODIFICATION_SYSTEM_MESSAGE",
        "You modify image prompts based on user requests.",
    )
