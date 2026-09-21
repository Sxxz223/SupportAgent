"""Fixed T7.2 evaluation cases. This module does not execute the Agent."""
from pathlib import Path

from .models import (
    AnswerRequirements,
    EvaluationCase,
    EvaluationExpectations,
    EvaluationTurn,
    FieldExpectation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHARGING_IMAGE = "test_images/charging_contacts.png"
CHARGING_TERMS = ("charge", "charging", "receiving power", "battery power")


def turn(user_input: str, image_path: str | None = None) -> EvaluationTurn:
    return EvaluationTurn(user_input=user_input, image_path=image_path)


EVALUATION_CASES: tuple[EvaluationCase, ...] = (
    EvaluationCase(
        id="case_01",
        name="Name alone requires identity verification",
        category="extraction",
        description="A known name alone must not disclose owned products.",
        turns=(turn("I'm Alice."),),
        expectations=EvaluationExpectations(
            expected_extraction={"user_name": "Alice"},
            expected_state={
                "user_name": "Alice",
                "customer_id": None,
                "identity_verified": False,
                "product": None,
                "product_id": None,
            },
            expected_stage="verify_identity",
            expected_allowed_tools_before_agent=("verify_customer",),
            answer_requirements=AnswerRequirements(must_not_claim=("your Anker Prime Charger", "you own")),
        ),
    ),
    EvaluationCase(
        id="case_unknown_customer_product",
        name="Unknown customer remains in product identification",
        category="extraction",
        description="An unknown demo customer lookup must not invent product ownership.",
        turns=(turn("I'm Bob."),),
        expectations=EvaluationExpectations(
            expected_extraction={"user_name": "Bob"},
            expected_state={"user_name": "Bob", "product": None, "product_id": None},
            expected_stage="verify_identity",
            expected_allowed_tools_before_agent=("verify_customer",),
            answer_requirements=AnswerRequirements(
                must_not_claim=("your Anker Prime Charger (250W, 6 Ports, GaNPrime)", "you own an Anker Prime Charger (250W, 6 Ports, GaNPrime)", "your product is Anker Prime Charger (250W, 6 Ports, GaNPrime)"),
            ),
        ),
    ),
    EvaluationCase(
        id="case_identity_phone",
        name="Verify identity with phone last four",
        category="workflow",
        description="A matching name and phone suffix establish identity without disclosing products.",
        initial_state={"user_name": "Alice"},
        turns=(turn("3721"),),
        expectations=EvaluationExpectations(
            expected_extraction={"phone_last4": "3721"},
            expected_state={"identity_verified": True, "customer_id": "00000000-0000-0000-0000-000000000001", "product": None},
            expected_stage="identify_product",
            expected_allowed_tools_before_agent=("verify_customer",),
            expected_tool_calls=("verify_customer",),
        ),
    ),
    EvaluationCase(
        id="case_identity_order",
        name="Verify identity with order number",
        category="workflow",
        description="A matching name and order number establish identity.",
        initial_state={"user_name": "Alice"},
        turns=(turn("My order number is ANK-DEMO-001."),),
        expectations=EvaluationExpectations(
            expected_extraction={"order_no": "ANK-DEMO-001"},
            expected_state={"identity_verified": True, "customer_id": "00000000-0000-0000-0000-000000000001"},
            expected_stage="identify_product",
            expected_allowed_tools_before_agent=("verify_customer",),
            expected_tool_calls=("verify_customer",),
        ),
    ),
    EvaluationCase(
        id="case_identity_wrong_phone",
        name="Reject incorrect identity evidence",
        category="boundary",
        description="An incorrect phone suffix keeps identity unverified and product hidden.",
        initial_state={"user_name": "Alice"},
        turns=(turn("9999"),),
        expectations=EvaluationExpectations(
            expected_extraction={"phone_last4": "9999"},
            expected_state={"identity_verified": False, "customer_id": None, "product": None},
            expected_stage="verify_identity",
            expected_allowed_tools_before_agent=("verify_customer",),
            expected_tool_calls=("verify_customer",),
            answer_requirements=AnswerRequirements(must_not_claim=("your Anker Prime Charger", "you own")),
        ),
    ),
    EvaluationCase(
        id="case_verified_owned_products",
        name="Verified customer can load owned products",
        category="tool",
        description="Only a verified customer ID can be used for ownership lookup.",
        initial_state={"user_name": "Alice", "customer_id": "00000000-0000-0000-0000-000000000001", "identity_verified": True},
        turns=(turn("Which product do I own?"),),
        expectations=EvaluationExpectations(
            expected_state={"product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)", "product_id": "anker-prime-250w"},
            expected_stage="understand_issue",
            expected_allowed_tools_before_agent=("get_owned_products",),
            expected_tool_calls=("get_owned_products",),
        ),
    ),
    EvaluationCase(
        id="case_02",
        name="Extract complete charging issue",
        category="extraction",
        description="Extract name, product, and a semantically charging-related issue.",
        turns=(turn("I'm Alice. My Anker Prime Charger (250W, 6 Ports, GaNPrime) won't charge."),),
        expectations=EvaluationExpectations(
            expected_state={"user_name": "Alice", "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"},
            expected_state_fields={
                "issue": FieldExpectation(contains_any=CHARGING_TERMS),
            },
            expected_stage="verify_identity",
            expected_allowed_tools_before_agent=("verify_customer",),
        ),
    ),
    EvaluationCase(
        id="case_03",
        name="Workflow requests identity",
        category="workflow",
        description="A vague request without identity remains in identify_user.",
        turns=(turn("I need some help."),),
        expectations=EvaluationExpectations(
            expected_stage="identify_user",
            expected_allowed_tools_before_agent=(),
        ),
    ),
    EvaluationCase(
        id="case_04",
        name="Workflow requests issue",
        category="workflow",
        description="A known customer who identifies a product advances to issue discovery.",
        initial_state={"user_name": "Alice", "customer_id": "00000000-0000-0000-0000-000000000001", "identity_verified": True},
        turns=(turn("My product is Anker Prime Charger (250W, 6 Ports, GaNPrime)."),),
        expectations=EvaluationExpectations(
            expected_state={"user_name": "Alice", "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"},
            expected_stage="understand_issue",
            expected_allowed_tools_before_agent=(),
        ),
    ),
    EvaluationCase(
        id="case_05",
        name="Workflow enters diagnosis",
        category="workflow",
        description="A customer and product with a newly stated issue enter diagnose.",
        initial_state={"user_name": "Alice", "customer_id": "00000000-0000-0000-0000-000000000001", "identity_verified": True, "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"},
        turns=(turn("It won't charge."),),
        expectations=EvaluationExpectations(
            expected_state_fields={
                "issue": FieldExpectation(contains_any=CHARGING_TERMS),
            },
            expected_stage="diagnose",
            expected_allowed_tools_before_agent=("check_warranty", "create_ticket"),
        ),
    ),
    EvaluationCase(
        id="case_06",
        name="Three-turn state continuity",
        category="multi_turn",
        description="Name, product, and issue accumulate across one persistent session.",
        initial_state={"user_name": "Alice", "customer_id": "00000000-0000-0000-0000-000000000001", "identity_verified": True},
        turns=(
            turn("I'm Alice."),
            turn("I have an Anker Prime Charger (250W, 6 Ports, GaNPrime)."),
            turn("It isn't receiving power."),
        ),
        expectations=EvaluationExpectations(
            expected_state={"user_name": "Alice", "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"},
            expected_state_fields={
                "issue": FieldExpectation(contains_any=CHARGING_TERMS),
            },
            expected_stage="diagnose",
            expected_rag_sources=("anker_prime_250w/charging_power.md",),
        ),
    ),
    EvaluationCase(
        id="case_07",
        name="Prime clock display retrieval",
        category="retrieval",
        description="A Prime clock question retrieves only Prime display guidance.",
        initial_state={"user_name": "Alice", "customer_id": "00000000-0000-0000-0000-000000000001", "identity_verified": True},
        turns=(turn("The clock screensaver on my Anker Prime 250W does not appear."),),
        expectations=EvaluationExpectations(
            expected_stage="diagnose",
            expected_rag_sources=("anker_prime_250w/display_clock.md",),
        ),
    ),
    EvaluationCase(
        id="case_08",
        name="Nano 70W power retrieval",
        category="retrieval",
        description="A Nano multi-port power question retrieves Nano power distribution knowledge.",
        initial_state={"user_name": "Alice", "customer_id": "00000000-0000-0000-0000-000000000001", "identity_verified": True, "product": "Anker Nano Charger (70W, 3 Ports)"},
        turns=(turn("Why does my laptop charge slowly when I use several ports?"),),
        expectations=EvaluationExpectations(
            expected_stage="diagnose",
            expected_rag_sources=("anker_nano_70w/power_distribution.md",),
        ),
    ),
    EvaluationCase(
        id="case_liberty_pairing",
        name="Liberty 4 NC pairing retrieval",
        category="retrieval",
        description="A Liberty pairing problem retrieves the earbuds pairing and reset guidance.",
        initial_state={"user_name": "Alice", "customer_id": "00000000-0000-0000-0000-000000000001", "identity_verified": True, "product": "soundcore Liberty 4 NC"},
        turns=(turn("My earbuds will not pair and the two sides are not syncing."),),
        expectations=EvaluationExpectations(
            expected_stage="diagnose",
            expected_rag_sources=("liberty_4_nc/pairing_reset.md",),
        ),
    ),
    EvaluationCase(
        id="case_09",
        name="Image-only perception",
        category="vision",
        description="The existing charging fixture enters Vision without unstable wording checks.",
        turns=(turn("", CHARGING_IMAGE),),
        expectations=EvaluationExpectations(
            expected_state={"image_received": True},
            expected_state_fields={
                "contacts_dirty": FieldExpectation(must_be_present=True),
                "indicator_on": FieldExpectation(must_be_present=True),
            },
            vision_used=True,
            expected_vision_fields=("contacts_dirty", "indicator_on"),
        ),
    ),
    EvaluationCase(
        id="case_10",
        name="Combined text and image perception",
        category="vision",
        description="Text extraction and image perception both update the same turn before decisions.",
        initial_state={"user_name": "Alice", "customer_id": "00000000-0000-0000-0000-000000000001", "identity_verified": True},
        turns=(turn("My Anker Prime Charger (250W, 6 Ports, GaNPrime) won't charge.", CHARGING_IMAGE),),
        expectations=EvaluationExpectations(
            expected_state={"product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)", "image_received": True},
            expected_state_fields={
                "issue": FieldExpectation(contains_any=CHARGING_TERMS),
                "contacts_dirty": FieldExpectation(must_be_present=True),
            },
            expected_stage="diagnose",
            vision_used=True,
            expected_vision_fields=("contacts_dirty",),
            answer_requirements=AnswerRequirements(must_mention=("charging contacts",)),
        ),
    ),
    EvaluationCase(
        id="case_11",
        name="Warranty lookup is available after failed troubleshooting",
        category="tool",
        description="The diagnose workflow exposes warranty lookup after troubleshooting failed; invocation remains Agent-selected.",
        initial_state={
            "user_name": "Alice",
            "customer_id": "00000000-0000-0000-0000-000000000001",
            "identity_verified": True,
            "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)",
            "issue": "won't charge",
            "attempted_steps": ["cleaned contacts", "repositioned robot", "restarted robot"],
        },
        turns=(turn("I tried all of those steps and it still won't charge."),),
        expectations=EvaluationExpectations(
            expected_stage="diagnose",
            expected_allowed_tools_before_agent=("check_warranty", "create_ticket"),
            answer_requirements=AnswerRequirements(must_mention=("warranty",)),
        ),
        notes="The current workflow permits check_warranty but the Main Agent decides whether to call it.",
    ),
    EvaluationCase(
        id="case_12",
        name="Explicit repair ticket request",
        category="tool",
        description="A complete business state and explicit request should create one repair ticket.",
        initial_state={"user_name": "Alice", "customer_id": "00000000-0000-0000-0000-000000000001", "identity_verified": True, "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)", "issue": "won't charge"},
        turns=(turn("Please create a repair ticket."),),
        expectations=EvaluationExpectations(
            expected_stage="diagnose",
            expected_allowed_tools_before_agent=("check_warranty", "create_ticket"),
            expected_tool_calls=("create_ticket",),
            expected_state_fields={"ticket_id": FieldExpectation(must_be_present=True)},
            answer_requirements=AnswerRequirements(must_mention=("ticket",)),
        ),
    ),
    EvaluationCase(
        id="case_13",
        name="Duplicate repair ticket is blocked",
        category="tool",
        description="An existing ticket removes create_ticket permission and prevents duplication.",
        initial_state={
            "user_name": "Alice", "customer_id": "00000000-0000-0000-0000-000000000001", "identity_verified": True, "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)", "issue": "won't charge",
            "ticket_id": "A20260916001",
        },
        turns=(turn("Create another ticket."),),
        expectations=EvaluationExpectations(
            expected_state={"ticket_id": "A20260916001"},
            expected_stage="diagnose",
            expected_allowed_tools_before_agent=("check_warranty",),
            forbidden_tools=("create_ticket",),
            answer_requirements=AnswerRequirements(must_not_claim=("created another ticket",)),
        ),
    ),
    EvaluationCase(
        id="case_14",
        name="Unsupported product capability boundary",
        category="boundary",
        description="The Agent must not invent a coffee-making capability without supporting knowledge.",
        initial_state={"user_name": "Alice", "customer_id": "00000000-0000-0000-0000-000000000001", "identity_verified": True, "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"},
        turns=(turn("Can the Anker Prime Charger (250W, 6 Ports, GaNPrime) make coffee?"),),
        expectations=EvaluationExpectations(
            expected_stage="diagnose",
            answer_requirements=AnswerRequirements(
                must_not_claim=("can make coffee", "coffee-making feature"),
            ),
        ),
    ),
    EvaluationCase(
        id="case_15",
        name="Product correction replaces old context",
        category="boundary",
        description="A stated product correction should replace Anker Prime Charger (250W, 6 Ports, GaNPrime) without leaking the old product context.",
        initial_state={"user_name": "Alice", "customer_id": "00000000-0000-0000-0000-000000000001", "identity_verified": True, "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"},
        turns=(turn("Actually my device is M1 Pro."),),
        expectations=EvaluationExpectations(
            expected_state={"product": "M1 Pro"},
            expected_stage="understand_issue",
            answer_requirements=AnswerRequirements(must_not_claim=("your Anker Prime Charger (250W, 6 Ports, GaNPrime)",)),
        ),
    ),
)


def get_case(case_id: str) -> EvaluationCase:
    """Return one fixed case by id."""
    return next(case for case in EVALUATION_CASES if case.id == case_id)


def resolve_image_path(turn: EvaluationTurn) -> Path | None:
    """Resolve a case image fixture without embedding machine-specific paths."""
    return PROJECT_ROOT / turn.image_path if turn.image_path else None
