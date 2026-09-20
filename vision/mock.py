from schemas.vision import VisionUpdate

def analyze_image_mock(image_path: str) -> VisionUpdate:
    """
    Mock vision analyzer.
    Later we replace this with a real multimodal model.
    """

    print(f"[VISION] analyzing: {image_path}")

    return VisionUpdate(
        dock_visible=True,
        indicator_on=True,
        contacts_dirty=True,
        robot_on_dock=True,
        observation=(
            "The charging dock is visible. "
            "The indicator light appears on. "
            "The charging contacts appear dirty."
        ),
    )
