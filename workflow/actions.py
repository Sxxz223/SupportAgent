from ..schemas.state import SupportState

def can_create_ticket(state: SupportState) -> bool:
    """
    判断是否满足创建售后 ticket 的基本条件
    """
    return (
        state.user_name is not None
        and state.identity_verified
        and state.customer_id is not None
        and state.product is not None
        and state.issue is not None
    )

def decide_next_action(state: SupportState) -> str:

    if (
        state.issue is not None
        and any(
            phrase in state.issue.lower()
            for phrase in ("charge", "charging", "receiving power")
        )
    ):
        if state.indicator_on is False:
            return "check_dock_power"

        if state.contacts_dirty is True:
            return "clean_charging_contacts"

        if state.robot_on_dock is False:
            return "reposition_robot"

    return "continue_diagnosis"
