"""Thin Agents SDK wrappers around replaceable support services."""
import json

from agents.decorators import tool
from agents.tool_context import ToolContext

from application.context import AppContext
from schemas.state import SupportState
from services.customer_service import CustomerService, get_customer_service
from services.ticket_service import TicketService, get_ticket_service
from trace.recorder import trace_tool_call


def verify_identity(
    state: SupportState,
    phone_last4: str | None = None,
    order_no: str | None = None,
    service: CustomerService | None = None,
) -> str:
    """Verify the stated identity without returning ownership data."""
    print(f"[TOOL] verify_customer called: {state.user_name or 'unknown'}")
    phone_last4 = phone_last4 or state.phone_last4
    order_no = order_no or state.order_no
    result = (service or get_customer_service()).verify_customer(
        name=state.user_name,
        phone_last4=phone_last4,
        order_no=order_no,
    )
    if result.verified:
        state.customer_id = result.customer_id
        state.identity_verified = True
    else:
        state.customer_id = None
        state.identity_verified = False
    return json.dumps(result.to_dict())


def load_owned_products(
    state: SupportState,
    customer_id: str,
    service: CustomerService | None = None,
) -> str:
    """Load ownership only for the customer verified in this session."""
    if not state.identity_verified or not state.customer_id or customer_id != state.customer_id:
        return json.dumps({"found": False, "error": "identity_not_verified", "products": []})
    products = (service or get_customer_service()).get_owned_products(customer_id)
    state.owned_products = [product.__dict__.copy() for product in products]
    state.ownership_lookup_completed = True
    if len(products) == 1:
        state.product = products[0].display_name
        state.product_id = products[0].product_id
    return json.dumps({
        "customer_id": customer_id,
        "found": bool(products),
        "products": state.owned_products,
    })


def find_warranty_status(
    state: SupportState,
    product: str,
    service: CustomerService | None = None,
) -> str:
    """Read warranty facts from the customer data source, never from constants."""
    print(f"[TOOL] check_warranty called: {product}")
    customer_service = service or get_customer_service()
    if not state.identity_verified or not state.customer_id:
        return json.dumps({"found": False, "status": None, "expires_at": None})
    result = customer_service.get_warranty_for_customer(state.customer_id, product)
    if result.found:
        state.warranty_status = result.status
    return json.dumps(result.to_dict())


def open_ticket(
    state: SupportState,
    product: str,
    issue: str,
    service: TicketService | None = None,
) -> str:
    """Create one ticket through the configured repository and persist its returned ID."""
    if state.ticket_id is not None:
        return json.dumps({
            "created": False,
            "already_exists": True,
            "ticket_id": state.ticket_id,
        })

    print(f"[TOOL] create_ticket called: product={product}, issue={issue}")
    result = (service or get_ticket_service()).create_ticket(product, issue)
    if result.created:
        state.ticket_id = result.ticket_id
    return json.dumps(result.to_dict())


@tool
def verify_customer(
    ctx: ToolContext[AppContext],
    phone_last4: str | None = None,
    order_no: str | None = None,
) -> str:
    """Verify the stated customer using a phone suffix or order number."""
    session = ctx.context.session
    result = trace_tool_call(
        session,
        "verify_customer",
        {"phone_last4": phone_last4, "order_no": order_no},
        lambda: verify_identity(
            session.state, phone_last4, order_no, ctx.context.customer_service
        ),
    )
    payload = json.loads(result)
    if payload.get("verified"):
        session.record_event(
            "identity_verified",
            customer_id=session.state.customer_id,
        )
    elif payload.get("status") == "AMBIGUOUS":
        session.record_event("identity_verification_ambiguous")
    else:
        session.record_event("identity_verification_failed")
    return result


@tool
def get_owned_products(ctx: ToolContext[AppContext], customer_id: str) -> str:
    """Return products for the customer already verified in this session."""
    session = ctx.context.session
    result = trace_tool_call(
        session,
        "get_owned_products",
        {"customer_id": customer_id},
        lambda: load_owned_products(
            session.state, customer_id, ctx.context.customer_service
        ),
    )
    payload = json.loads(result)
    if payload.get("found"):
        session.record_event(
            "product_lookup_succeeded",
            product=session.state.product,
            product_id=session.state.product_id,
            products=session.state.owned_products,
        )
    elif payload.get("error") != "identity_not_verified":
        session.record_event("product_lookup_not_found")
    return result


# Import compatibility only. The SDK tool name and business contract are get_owned_products.
get_product = get_owned_products


@tool
def check_warranty(ctx: ToolContext[AppContext], product: str) -> str:
    """Check whether a product is still under warranty."""
    session = ctx.context.session
    result = trace_tool_call(
        session,
        "check_warranty",
        {"product": product},
        lambda: find_warranty_status(
            session.state,
            product,
            ctx.context.customer_service,
        ),
    )
    payload = json.loads(result)
    session.record_event(
        "warranty_lookup_succeeded" if payload.get("found") else "warranty_lookup_not_found",
        product=product,
        warranty_status=session.state.warranty_status,
    )
    return result


@tool
def create_ticket(ctx: ToolContext[AppContext], product: str, issue: str) -> str:
    """Create a repair ticket unless this session already has one."""
    session = ctx.context.session
    previous_ticket_id = session.state.ticket_id
    result = trace_tool_call(
        session,
        "create_ticket",
        {"product": product, "issue": issue},
        lambda: open_ticket(session.state, product, issue, ctx.context.ticket_service),
    )
    payload = json.loads(result)
    if previous_ticket_id is None and session.state.ticket_id is not None:
        session.record_event(
            "ticket_created",
            ticket_id=session.state.ticket_id,
            product=product,
        )
    elif not payload.get("already_exists"):
        session.record_event("ticket_creation_failed", reason=payload.get("error"))
    return result
