import logging
import os

import aiofiles
import replicate
import replicate.helpers

from slopbox.base import ASPECT_TO_RECRAFT, IMAGE_DIR
from slopbox.model import update_generation_status

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

replicate_client = replicate.Client(api_token=os.environ.get("REPLICATE_API_KEY"))


async def generate_image(
    generation_id: str, prompt: str, aspect_ratio: str, model: str, style: str
):
    """Background task to generate the image and update the database."""
    try:
        logger.info(f"Starting image generation for ID: {generation_id}")
        logger.info(
            f"Using model: {model}, aspect ratio: {aspect_ratio}, style: {style}"
        )

        # Set up model inputs
        model_inputs = {
            "prompt": prompt,
            "disable_safety_checker": True,
            "output_format": "png",
            "raw": True,
        }

        # Handle model-specific parameters
        if "recraft" in model:
            model_inputs["size"] = ASPECT_TO_RECRAFT[aspect_ratio]
            style_map = {
                "natural": "realistic_image/natural_light",
                "studio": "realistic_image/studio_portrait",
                "flash": "realistic_image/hard_flash",
                "illustration": "digital_illustration/grain",
            }
            model_inputs["style"] = style_map.get(
                style, "realistic_image/natural_light"
            )
            logger.info(f"Using Recraft style={model_inputs['style']}")
        else:
            model_inputs["aspect_ratio"] = aspect_ratio
            model_inputs["safety_tolerance"] = 6
            logger.info(f"Using standard settings with aspect_ratio={aspect_ratio}")

        logger.info("Calling Replicate API to generate image...")
        # Generate the image
        output = await replicate_client.async_run(
            model,
            input=model_inputs,
        )

        logger.info("Image generated successfully, downloading result...")
        # Read the image bytes
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
