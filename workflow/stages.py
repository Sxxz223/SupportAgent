from ..schemas.state import SupportState, StateUpdate
from ..schemas.vision import VisionUpdate
from ..tools.support_tools import verify_customer, get_owned_products, check_warranty, create_ticket
from ..products.catalog import resolve_product

def next_stage(state: SupportState) -> str:
    """
    根据当前业务状态，决定 workflow 走到哪一步
    """

    if state.user_name is None:
        return "identify_user"

    if not state.identity_verified or state.customer_id is None:
        return "verify_identity"

    if state.product is None:
        return "identify_product"

    if state.issue is None:
        return "understand_issue"

    if not state.resolved:
        return "diagnose"

    return "resolved"

def apply_update(state: SupportState, update: StateUpdate):
    """
    把这一轮新提取的信息合并进总 State
    """

    if update.user_name is not None:
        if state.user_name is not None and update.user_name.casefold() != state.user_name.casefold():
            state.customer_id = None
            state.identity_verified = False
            state.phone_last4 = None
            state.order_no = None
            state.product = None
            state.product_id = None
            state.owned_products = []
            state.ownership_lookup_completed = False
            state.warranty_status = None
        state.user_name = update.user_name

    if update.phone_last4 is not None:
        state.phone_last4 = update.phone_last4

    if update.order_no is not None:
        state.order_no = update.order_no

    if update.product is not None:
        catalog_product = resolve_product(update.product)
        state.product = catalog_product.display_name if catalog_product else update.product
        state.product_id = catalog_product.product_id if catalog_product else None
    elif state.product is not None and state.product_id is None:
        catalog_product = resolve_product(state.product)
        if catalog_product:
            state.product = catalog_product.display_name
            state.product_id = catalog_product.product_id

    if update.issue is not None:
        state.issue = update.issue

    for key, fact in update.facts.items():
        state.diagnostic_facts[key] = fact.value
        if key == "attempted_steps":
            steps = fact.value if isinstance(fact.value, list) else [fact.value]
            for step in steps:
                if isinstance(step, str) and step not in state.attempted_steps:
                    state.attempted_steps.append(step)

def apply_vision_update(
    state: SupportState,
    update: VisionUpdate
):
    state.image_received = True

    if update.dock_visible is not None:
        state.dock_visible = update.dock_visible

    if update.indicator_on is not None:
        state.indicator_on = update.indicator_on

    if update.contacts_dirty is not None:
        state.contacts_dirty = update.contacts_dirty

    if update.robot_on_dock is not None:
        state.robot_on_dock = update.robot_on_dock

def get_allowed_tools(state: SupportState):
    current_stage = state.stage
    if state.user_name is None or current_stage == "identify_user":
    
        allowed_tools = []
    
        allowed_tool_names = []
    
    
    elif not state.identity_verified or state.customer_id is None:
    
        allowed_tools = [
            verify_customer,
        ]
    
        allowed_tool_names = [
            "verify_customer",
        ]
    
    
    elif current_stage == "identify_product" and not state.ownership_lookup_completed:
    
        allowed_tools = [
            get_owned_products,
        ]
    
        allowed_tool_names = [
            "get_owned_products",
        ]
    
    
    elif current_stage == "understand_issue":
    
        allowed_tools = []
    
        allowed_tool_names = []
    
    
    elif current_stage == "diagnose":
    
        allowed_tools = [
            check_warranty,
        ]
    
        allowed_tool_names = [
            "check_warranty",
        ]

        if state.ticket_id is None:
            allowed_tools.append(create_ticket)
            allowed_tool_names.append("create_ticket")
    
    
    else:
    
        allowed_tools = []
    
        allowed_tool_names = []
    
    
    return allowed_tools, allowed_tool_names
