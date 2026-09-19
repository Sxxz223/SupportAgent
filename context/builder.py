"""Select and format program-owned facts for the Main Agent."""
from collections.abc import Sequence
from typing import Any

from ..application.events import RuntimeEvent
from ..application.session import TurnContext
from ..schemas.state import SupportState


IMPORTANT_ACTION_EVENTS = {
    "identity_verified",
    "product_lookup_succeeded",
    "warranty_lookup_succeeded",
    "ticket_created",
}


def _format_value(value: Any) -> str:
    if value is None:
        return "unknown"
    return str(value)


def _latest_event(events: Sequence[RuntimeEvent], event_type: str) -> RuntimeEvent | None:
    return next((event for event in reversed(events) if event.event_type == event_type), None)


def _important_previous_actions(events: Sequence[RuntimeEvent]) -> list[str]:
    """Keep only the latest occurrence of each important action type."""
    latest_by_type: dict[str, RuntimeEvent] = {}
    for event in events:
        if event.event_type in IMPORTANT_ACTION_EVENTS:
            latest_by_type[event.event_type] = event

    lines = []
    for event in sorted(latest_by_type.values(), key=lambda item: item.turn_index):
        details = ", ".join(
            f"{key}={_format_value(value)}" for key, value in event.data.items()
        )
        suffix = f" ({details})" if details else ""
        lines.append(f"- turn {event.turn_index}: {event.event_type}{suffix}")
    return lines or ["- none"]


def _recent_conversation(history: Sequence[dict[str, Any]]) -> list[str]:
    """Expose at most the last completed exchange, with bounded message length."""
    lines = []
    for item in history[-2:]:
        role = str(item.get("role", "unknown"))
        content = str(item.get("content", ""))[:500]
        lines.append(f"- {role}: {content}")
    return lines or ["- none"]


def build_model_context(
    state: SupportState,
    turn: TurnContext,
    events: Sequence[RuntimeEvent],
    history: Sequence[dict[str, Any]],
) -> str:
    """Build a stable model view without changing any program-owned data."""
    if turn.vision_update is not None:
        vision = turn.vision_update
        current_evidence = [
            "- source: image analyzed in the current turn",
            f"- dock_visible: {_format_value(vision.dock_visible)}",
            f"- indicator_on: {_format_value(vision.indicator_on)}",
            f"- contacts_dirty: {_format_value(vision.contacts_dirty)}",
            f"- robot_on_dock: {_format_value(vision.robot_on_dock)}",
            f"- observation: {_format_value(vision.observation)}",
        ]
        historical_evidence = ["- not included while current-turn image evidence is available"]
    else:
        current_evidence = ["- no image was provided or analyzed in the current turn"]
        previous_vision = _latest_event(events, "vision_analyzed")
        if previous_vision is None:
            historical_evidence = ["- none"]
        else:
            historical_evidence = [
                f"- source: historical image observation from turn {previous_vision.turn_index}",
                "- this was not observed in the current turn",
                *[
                    f"- {key}: {_format_value(value)}"
                    for key, value in previous_vision.data.items()
                ],
            ]

    allowed_tools = ", ".join(turn.allowed_tool_names) or "none"
    knowledge = turn.retrieved_knowledge or "none"

    sections = [
        "Current Business State:",
        f"- user_name: {_format_value(state.user_name)}",
        f"- customer_id: {_format_value(state.customer_id)}",
        f"- identity_verified: {state.identity_verified}",
        f"- phone_last4: {_format_value(state.phone_last4)}",
        f"- order_no: {_format_value(state.order_no)}",
        f"- product: {_format_value(state.product)}",
        f"- product_id: {_format_value(state.product_id)}",
        "- owned_products:",
        *(
            [
                "  - " + ", ".join(
                    f"{key}={_format_value(product.get(key))}"
                    for key in (
                        "product_id", "product_name", "model", "order_number",
                        "purchase_date", "warranty_status", "warranty_until",
                    )
                    if product.get(key) is not None
                )
                for product in state.owned_products
            ] or ["  - none"]
        ),
        f"- issue: {_format_value(state.issue)}",
        f"- stage: {state.stage}",
        f"- warranty_status: {_format_value(state.warranty_status)}",
        f"- ticket_id: {_format_value(state.ticket_id)}",
        f"- attempted_steps: {state.attempted_steps}",
        f"- resolved: {state.resolved}",
        "",
        "Current Turn:",
        f"- user_input: {turn.user_input}",
        f"- image_provided: {bool(turn.image_path)}",
        f"- next_action: {turn.next_action}",
        f"- allowed_tools: {allowed_tools}",
        "",
        "Current-turn Evidence:",
        *current_evidence,
        "",
        "Historical Visual Evidence:",
        *historical_evidence,
        "",
        "Retrieved Knowledge (current turn):",
        knowledge,
        "",
        "Important Previous Actions:",
        *_important_previous_actions(events),
        "",
        "Recent Conversation (last completed exchange only):",
        *_recent_conversation(history),
    ]
    return "\n".join(sections)
