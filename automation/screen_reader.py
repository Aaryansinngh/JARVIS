"""
automation/screen_reader.py — Understand screen content with GPT-4o Vision

Takes a screenshot → sends to GPT-4o Vision → returns understanding.
This enables Jarvis to:
  - Read error messages it can't click
  - Describe what's on screen
  - Find specific UI elements
  - Answer "what is on my screen right now?"
"""
import base64
import os
from pathlib import Path
from PIL import ImageGrab
from utils.logger import logger
from utils.config import get


class ScreenReader:
    """Use GPT-4o Vision to understand the screen."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            api_key = get("ai", "openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def _screenshot_to_base64(self, region=None) -> str:
        """Capture screen and return as base64 string."""
        img = ImageGrab.grab(bbox=region)
        # Resize to reduce API tokens/cost
        img = img.resize((1280, 720))

        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def describe_screen(self, question: str = "What is on the screen?") -> str:
        """
        Take a screenshot and answer a question about it.

        Usage:
            reader.describe_screen("What error message is shown?")
            reader.describe_screen("Is there a login button on screen?")
            reader.describe_screen("What application is open?")
        """
        logger.info(f"Reading screen: '{question}'")
        client = self._get_client()

        image_b64 = self._screenshot_to_base64()

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                                "detail": "high",
                            },
                        },
                        {"type": "text", "text": question},
                    ],
                }
            ],
            max_tokens=500,
        )

        answer = response.choices[0].message.content
        logger.info(f"Screen AI answer: {answer[:100]}")
        return answer

    def find_element(self, element_description: str) -> dict:
        """
        Find a UI element on screen.
        Returns {"found": bool, "description": str, "suggested_action": str}
        """
        question = (
            f"Look for: '{element_description}'. "
            "If found, describe exactly where it is on screen (top-left, center, etc.) "
            "and what action to take. "
            "Respond in JSON: {\"found\": true/false, \"location\": \"...\", \"action\": \"...\"}"
        )
        result = self.describe_screen(question)
        try:
            import json
            return json.loads(result)
        except Exception:
            return {"found": False, "description": result, "suggested_action": ""}

    def read_text_on_screen(self) -> str:
        """Extract all readable text from the current screen."""
        return self.describe_screen(
            "Please read and return ALL the text visible on this screen, "
            "preserving the general layout. Include error messages, labels, and button text."
        )
