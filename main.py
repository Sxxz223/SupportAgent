"""Simple multi-turn CLI for the customer support demo."""
from application.turn_processor import process_turn
from application.session import SupportSession


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
