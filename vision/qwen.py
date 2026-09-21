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
    image_path: str, qwen_vision_client,
    visual_context: dict | None = None,
    existing_facts: dict | None = None,
) -> VisionUpdate:

    print(f"[QWEN VISION] analyzing: {image_path}")

    image_data_url = image_to_data_url(image_path)

    visual_context = visual_context or {}
    requested_fields = visual_context.get("fields") or [
        "product_model", "current_port", "power_reading", "screen_state", "physical_damage",
    ]
    request_description = {
        "target": visual_context.get("target") or "当前产品及其可见状态",
        "extract_fields": requested_fields,
        "existing_facts": existing_facts or {},
    }
    prompt = f"""
Analyze this customer-support image for the current task only.
Current visual request:
{json.dumps(request_description, ensure_ascii=False)}

Return ONLY valid JSON in this shape:
{{
  "fields": [
    {{"key":"product_model","label":"产品型号","value":"A2345","status":"recognized","source":"image"}}
  ],
  "reshoot_target": null,
  "conflicts": [],
  "observation": "brief description of only relevant visible evidence"
}}

Rules:
- Return one field for every requested extract_fields item and no unrelated fields.
- status is recognized only when the value is visually clear; otherwise use unclear or failed and value null.
- Do not guess hidden properties or diagnose a root cause.
- If only part is unclear, keep recognized fields and set reshoot_target to the smallest area that needs another photo.
- Compare with existing_facts only when a visible value clearly differs. Put material differences in conflicts.
- Do not output confidence numbers, markdown, or prose outside JSON.
"""

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
                        "text": prompt,
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
