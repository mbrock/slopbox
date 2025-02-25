import os

import anthropic

from slopbox.base import prompt_modification_system_message

claude = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


async def generate_modified_prompt(modification, prompt):
    message = await claude.messages.create(
        max_tokens=1024,
        model="claude-3-5-sonnet-latest",
        system=prompt_modification_system_message(),
        messages=[
            {
                "role": "user",
                "content": f"<original-prompt>{prompt}</original-prompt>\n<modification-request>{modification}</modification-request>",
            }
        ],
        tools=[
            {
                "name": "replacePromptText",
                "description": "Replace the original prompt with a modified version based on the modification request",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "modified_prompt": {
                            "type": "string",
                            "description": "The modified version of the original prompt",
                        }
                    },
                    "required": ["modified_prompt"],
                },
            }
        ],
    )

    print(message)

    # Extract the modified prompt from the tool use response
    modified_prompt = None
    for content in message.content:
        if content.type == "tool_use" and content.name == "replacePromptText":
            assert isinstance(content.input, dict)
            modified_prompt = content.input["modified_prompt"]
            break
    return modified_prompt
