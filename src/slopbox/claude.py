import os

import rich
from openai import AsyncOpenAI

from slopbox.base import prompt_modification_system_message

client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


async def generate_modified_prompt(modification, prompt):
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": prompt_modification_system_message(),
            },
            {
                "role": "user",
                "content": (
                    f"<original-prompt>{prompt}</original-prompt>\n"
                    f"<modification-request>{modification}</modification-request>"
                ),
            },
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "replacePromptText",
                    "description": (
                        "Replace the original prompt with a modified version "
                        "based on the modification request"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "modified_prompt": {
                                "type": "string",
                                "description": (
                                    "The modified version of the original prompt"
                                ),
                            }
                        },
                        "required": ["modified_prompt"],
                    },
                },
            }
        ],
        tool_choice="auto",
    )

    rich.print(response)

    # Extract the modified prompt from the tool use response
    modified_prompt = None
    if response.choices[0].message.tool_calls:
        for tool_call in response.choices[0].message.tool_calls:
            if tool_call.function.name == "replacePromptText":
                import json

                args = json.loads(tool_call.function.arguments)
                modified_prompt = args["modified_prompt"]
                break
    return modified_prompt
