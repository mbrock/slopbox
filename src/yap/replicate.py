from yap.base import ASPECT_TO_RECRAFT, IMAGE_DIR
from yap.model import update_generation_status


import aiofiles
import replicate


import os

replicate_client = replicate.Client(api_token=os.environ.get("REPLICATE_API_KEY"))


async def generate_image(
    generation_id: str, prompt: str, aspect_ratio: str, model: str, style: str
):
    """Background task to generate the image and update the database."""
    try:
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
        else:
            model_inputs["aspect_ratio"] = aspect_ratio
            model_inputs["safety_tolerance"] = 6

        # Generate the image
        output = await replicate_client.async_run(
            model,
            input=model_inputs,
        )

        # Read the image bytes
        if isinstance(output, list):
            image_bytes = await output[0].aread()
        else:
            image_bytes = await output.aread()

        # Save the image
        filename = f"{generation_id}.png"
        file_path = os.path.join(IMAGE_DIR, filename)
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(image_bytes)

        # Update the database
        update_generation_status(generation_id, "complete", file_path)

    except Exception as e:
        print(f"Error generating image: {e}")
        update_generation_status(generation_id, "error")
