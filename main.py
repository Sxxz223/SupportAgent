"""Simple multi-turn CLI for the customer support demo."""
from pathlib import Path

# Distinguish this project's agents package from the third-party Agents SDK.
# Also support `python /absolute/path/to/my_project/main.py` from any directory.
if not __package__:
    import importlib
    import sys
    project_dir = Path(__file__).resolve().parent
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != project_dir]
    sys.path.insert(0, str(project_dir.parent))
    __package__ = project_dir.name
    # Historical tests and integrations import this repository as
    # ``my_project`` even when the checkout directory is named SupportAgent.
    # Keep one canonical package object so both names share module state.
    package = importlib.import_module(__package__)
    sys.modules.setdefault("my_project", package)

from .application.turn_processor import process_turn
from .application.session import SupportSession


def main():
    session = SupportSession()

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "exit":
            break

        image_path = input("Image path (optional): ").strip() or None
        response = process_turn(session, user_input, image_path)
        print("\nAssistant:")
        print(response)


if __name__ == "__main__":
    main()
