import base64
import json
import mimetypes
from pathlib import Path
from ..schemas.vision import VisionUpdate

def image_to_data_url(image_path: str) -> str:
    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    mime_type = (
        mimetypes.guess_type(path.name)[0]
        or "image/jpeg"
    )

    encoded = base64.b64encode(
        path.read_bytes()
    ).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"

def analyze_image_qwen(
    image_path: str, qwen_vision_client
) -> VisionUpdate:

    print(f"[QWEN VISION] analyzing: {image_path}")

    image_data_url = image_to_data_url(image_path)

    response = qwen_vision_client.chat.completions.create(
        model="qwen3-vl-plus",

        messages=[
            {
                "role": "user",

                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url
                        },
                    },

                    {
                        "type": "text",
                        "text": """
Analyze this product-support image.

Return ONLY valid JSON:

{
  "dock_visible": null,
  "indicator_on": null,
  "contacts_dirty": null,
  "robot_on_dock": null,
  "observation": null
}

Rules:

- Only report visually observable facts.
- Do not guess hidden hardware problems.
- Use true or false only when reasonably clear.
- Otherwise use null.
- observation should briefly describe what is visible.
- Do not diagnose the root cause.
- Do not output markdown.
"""
                    },
                ],
            }
        ],
    )

    raw_output = (
        response.choices[0]
        .message.content
    )

    print("\n[RAW QWEN VISION OUTPUT]")
    print(raw_output)

    data = json.loads(raw_output)

    return VisionUpdate(**data)
