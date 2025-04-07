import asyncio
import hashlib
import json
import logging
import os
import time
from enum import Enum
from io import BytesIO
from typing import Dict, Optional

import aiofiles
import aiohttp
import replicate
import replicate.helpers
from openai import AsyncOpenAI
from PIL import Image

from slopbox.base import ASPECT_TO_RECRAFT, DEFAULT_MODEL, IMAGE_DIR
from slopbox.model import update_generation_status

logger = logging.getLogger(__name__)


# Model providers
class ModelProvider(str, Enum):
    """Enum for available image generation providers."""

    REPLICATE = "replicate"
    RECRAFT = "recraft"


# Default models by provider
DEFAULT_MODELS = {
    ModelProvider.REPLICATE: "recraft-ai/recraft-v3",
    ModelProvider.RECRAFT: "recraft-v3",
}

# Default model provider based on the model name
DEFAULT_PROVIDER = (
    ModelProvider.RECRAFT
    if "recraft" in DEFAULT_MODEL.lower()
    else ModelProvider.REPLICATE
)

# Initialize OpenAI client for Recraft API
recraft_client = AsyncOpenAI(
    base_url="https://external.api.recraft.ai/v1",
    api_key=os.getenv("RECRAFT_API_TOKEN"),
)


class ImageStyle(str, Enum):
    """Enum for available image styles in the Recraft model."""

    ANY = "any"

    # Realistic image styles
    REALISTIC_IMAGE = "realistic_image"
    REALISTIC_BW = "realistic_image/b_and_w"
    REALISTIC_ENTERPRISE = "realistic_image/enterprise"
    REALISTIC_EVENING_LIGHT = "realistic_image/evening_light"
    REALISTIC_FADED_NOSTALGIA = "realistic_image/faded_nostalgia"
    REALISTIC_FOREST_LIFE = "realistic_image/forest_life"
    REALISTIC_HARD_FLASH = "realistic_image/hard_flash"
    REALISTIC_HDR = "realistic_image/hdr"
    REALISTIC_MOTION_BLUR = "realistic_image/motion_blur"
    REALISTIC_MYSTIC_NATURALISM = "realistic_image/mystic_naturalism"
    REALISTIC_NATURAL_LIGHT = "realistic_image/natural_light"
    REALISTIC_NATURAL_TONES = "realistic_image/natural_tones"
    REALISTIC_ORGANIC_CALM = "realistic_image/organic_calm"
    REALISTIC_REAL_LIFE_GLOW = "realistic_image/real_life_glow"
    REALISTIC_RETRO_REALISM = "realistic_image/retro_realism"
    REALISTIC_RETRO_SNAPSHOT = "realistic_image/retro_snapshot"
    REALISTIC_STUDIO_PHOTO = "realistic_image/studio_photo"
    REALISTIC_STUDIO_PORTRAIT = "realistic_image/studio_portrait"
    REALISTIC_URBAN_DRAMA = "realistic_image/urban_drama"
    REALISTIC_VILLAGE_REALISM = "realistic_image/village_realism"
    REALISTIC_WARM_FOLK = "realistic_image/warm_folk"

    # Digital illustration styles
    DIGITAL_ILLUSTRATION = "digital_illustration"
    DIGITAL_PIXEL_ART = "digital_illustration/pixel_art"
    DIGITAL_HAND_DRAWN = "digital_illustration/hand_drawn"
    DIGITAL_GRAIN = "digital_illustration/grain"
    DIGITAL_GRAIN_20 = "digital_illustration/grain_20"
    DIGITAL_INFANTILE_SKETCH = "digital_illustration/infantile_sketch"
    DIGITAL_2D_ART_POSTER = "digital_illustration/2d_art_poster"
    DIGITAL_2D_ART_POSTER_2 = "digital_illustration/2d_art_poster_2"
    DIGITAL_HANDMADE_3D = "digital_illustration/handmade_3d"
    DIGITAL_HAND_DRAWN_OUTLINE = "digital_illustration/hand_drawn_outline"
    DIGITAL_ENGRAVING_COLOR = "digital_illustration/engraving_color"
    DIGITAL_ENGRAVING = "digital_illustration/digital_engraving"
    DIGITAL_ANTIQUARIAN = "digital_illustration/antiquarian"
    DIGITAL_BOLD_FANTASY = "digital_illustration/bold_fantasy"
    DIGITAL_CHILD_BOOK = "digital_illustration/child_book"
    DIGITAL_CHILD_BOOKS = "digital_illustration/child_books"
    DIGITAL_COVER = "digital_illustration/cover"
    DIGITAL_CROSSHATCH = "digital_illustration/crosshatch"
    DIGITAL_EXPRESSIONISM = "digital_illustration/expressionism"
    DIGITAL_FREEHAND_DETAILS = "digital_illustration/freehand_details"
    DIGITAL_GRAPHIC_INTENSITY = "digital_illustration/graphic_intensity"
    DIGITAL_HARD_COMICS = "digital_illustration/hard_comics"
    DIGITAL_LONG_SHADOW = "digital_illustration/long_shadow"
    DIGITAL_MODERN_FOLK = "digital_illustration/modern_folk"
    DIGITAL_MULTICOLOR = "digital_illustration/multicolor"
    DIGITAL_NEON_CALM = "digital_illustration/neon_calm"
    DIGITAL_NOIR = "digital_illustration/noir"
    DIGITAL_NOSTALGIC_PASTEL = "digital_illustration/nostalgic_pastel"
    DIGITAL_OUTLINE_DETAILS = "digital_illustration/outline_details"
    DIGITAL_PASTEL_GRADIENT = "digital_illustration/pastel_gradient"
    DIGITAL_PASTEL_SKETCH = "digital_illustration/pastel_sketch"
    DIGITAL_PLASTIC = "digital_illustration/plastic"
    DIGITAL_POP_ART = "digital_illustration/pop_art"
    DIGITAL_POP_RENAISSANCE = "digital_illustration/pop_renaissance"
    DIGITAL_SEAMLESS = "digital_illustration/seamless"
    DIGITAL_STREET_ART = "digital_illustration/street_art"
    DIGITAL_TABLET_SKETCH = "digital_illustration/tablet_sketch"
    DIGITAL_URBAN_GLOW = "digital_illustration/urban_glow"
    DIGITAL_URBAN_SKETCHING = "digital_illustration/urban_sketching"
    DIGITAL_VANILLA_DREAMS = "digital_illustration/vanilla_dreams"
    DIGITAL_YOUNG_ADULT_BOOK = "digital_illustration/young_adult_book"
    DIGITAL_YOUNG_ADULT_BOOK_2 = "digital_illustration/young_adult_book_2"


async def generate_image(
    generation_id: str, prompt: str, aspect_ratio: str, model: str, style: str
):
    """Background task to generate the image and update the database.

    Args:
        generation_id: The unique ID for this generation
        prompt: The text prompt for image generation
        aspect_ratio: The aspect ratio of the image (e.g. "1:1", "16:9")
        model: The model ID to use
        style: The style to use for the image

    Returns:
        None - updates the database with the results
    """
    try:
        logger.info(f"Starting image generation for ID: {generation_id}")
        logger.info(
            f"Using model: {model}, aspect ratio: {aspect_ratio}, style: {style}"
        )

        # Determine if we should use Replicate or Recraft based on the model name
        if "recraft" in model.lower():
            # Use Recraft via OpenAI API
            provider = ModelProvider.RECRAFT
            # Use the style directly from the form instead of mapping
            style_name = style if style in [s.value for s in ImageStyle] else "realistic_image/natural_light"

            # Get full style and substyle
            if "/" in style_name:
                style_category, substyle = style_name.split("/", 1)
            else:
                style_category, substyle = style_name, None

            logger.info(f"Using Recraft style={style_name}")

            # Initialize Recraft client
            recraft_client = AsyncOpenAI(
                base_url="https://external.api.recraft.ai/v1",
                api_key=os.environ.get("RECRAFT_API_TOKEN"),
            )

            # Use the OpenAI API to generate the image
            size_param = ASPECT_TO_RECRAFT[aspect_ratio]

            # Generate the image
            response = await recraft_client.images.generate(
                prompt=prompt,
                size="1024x1024",  # This will be overridden by extra_body params
                extra_body={
                    "size": size_param,
                    "style": style_category,
                    "substyle": substyle,
                },
            )

            # Download the image from the URL
            if response.data and response.data[0].url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(response.data[0].url) as resp:
                        image_bytes = await resp.read()
            else:
                raise ValueError("No image URL returned from Recraft API")

        else:
            # Use Replicate for all other models
            provider = ModelProvider.REPLICATE

            # Set up model inputs for Replicate
            model_inputs = {
                "prompt": prompt,
                "disable_safety_checker": True,
                "output_format": "png",
                "raw": True,
            }

            # Add aspect ratio parameter for Replicate models
            if "recraft" in model:
                model_inputs["size"] = ASPECT_TO_RECRAFT[aspect_ratio]
            else:
                model_inputs["aspect_ratio"] = aspect_ratio
                model_inputs["safety_tolerance"] = 6

            logger.info(f"Using Replicate with aspect_ratio={aspect_ratio}")

            # Initialize Replicate client
            replicate_client = replicate.Client(
                api_token=os.environ.get("REPLICATE_API_KEY")
            )

            logger.info("Calling Replicate API to generate image...")
            # Generate the image
            output = await replicate_client.async_run(
                model,
                input=model_inputs,
            )

            logger.info("Image generated successfully, downloading result...")
            # Handle Replicate output
            if isinstance(output, list):
                file_output = output[0]
            else:
                file_output = output

            assert isinstance(file_output, replicate.helpers.FileOutput)
            image_bytes = await file_output.aread()

        # Save the image
        filename = f"{generation_id}.png"
        file_path = os.path.join(IMAGE_DIR, filename)
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(image_bytes)
        logger.info(f"Image saved successfully to: {file_path}")

        # Update the database
        update_generation_status(generation_id, "complete", file_path)
        logger.info(f"Generation {generation_id} completed successfully")

    except Exception as e:
        logger.error(
            f"Error generating image for ID {generation_id}: {str(e)}", exc_info=True
        )
        update_generation_status(generation_id, "error")


# Initialize OpenAI client for Recraft API
recraft_client = AsyncOpenAI(
    base_url="https://external.api.recraft.ai/v1",
    api_key=os.environ.get("RECRAFT_API_TOKEN"),
)
