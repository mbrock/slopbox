import os
import sqlite3

MODELS = {
    "Flux 1.1 Pro Ultra": "black-forest-labs/flux-1.1-pro-ultra",
    "Flux Dev": "black-forest-labs/flux-dev",
    "Flux Schnell": "black-forest-labs/flux-schnell",
    "Recraft v3": "recraft-ai/recraft-v3",
}

ASPECT_TO_RECRAFT = {
    "1:1": "1024x1024",  # Square
    "16:9": "1820x1024",  # Widescreen
    "9:16": "1024x1820",  # Portrait
    "4:3": "1365x1024",  # Standard
    "3:4": "1024x1365",  # Portrait standard
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

IMAGE_DIR = os.path.expanduser("~/yap/img")
os.makedirs(IMAGE_DIR, exist_ok=True)

DB_PATH = os.path.expanduser("~/yap/img.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)


def create_tables():
    with conn:
        conn.execute(
            """
          CREATE TABLE IF NOT EXISTS images_v2 (
              id INTEGER PRIMARY KEY,
              uuid TEXT UNIQUE,
              prompt TEXT,
              filepath TEXT,
              status TEXT DEFAULT 'pending',
              model TEXT,
              aspect_ratio TEXT,
              created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
          )
          """
        )


def prompt_modification_system_message():
    return os.environ.get(
        "PROMPT_MODIFICATION_SYSTEM_MESSAGE",
        "You modify image prompts based on user requests.",
    )
