"""FastAPI transport for the existing support application."""
from pathlib import Path
import sys
import importlib.util
import os
from collections.abc import Callable
from tempfile import NamedTemporaryFile

# Support the requested `uvicorn api.app:app` command without allowing the
# project's `agents/` package to shadow the installed Agents SDK.
project_dir = Path(__file__).resolve().parents[1]


def _load_local_environment() -> None:
    """Load ignored local credentials without logging or overwriting shell values."""
    env_file = project_dir / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name.replace("_", "").isalnum():
            os.environ.setdefault(name, value)


_load_local_environment()
sys.path[:] = [
    path for path in sys.path
    if Path(path or ".").resolve() != project_dir
]
if str(project_dir.parent) not in sys.path:
    sys.path.insert(0, str(project_dir.parent))

# The repository may be cloned under any folder name. Register the package
# alias used by the existing imports so `uvicorn api.app:app` works in-place.
if "my_project" not in sys.modules:
    package_spec = importlib.util.spec_from_file_location(
        "my_project", project_dir / "__init__.py",
        submodule_search_locations=[str(project_dir)],
    )
    if package_spec and package_spec.loader:
        package = importlib.util.module_from_spec(package_spec)
        sys.modules["my_project"] = package
        package_spec.loader.exec_module(package)

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from my_project.api.schemas import (
    ChatRequest,
    ChatResponse,
    CustomerCreateRequest,
    CustomerDetailResponse,
    CustomerResponse,
    CustomerUpdateRequest,
    HealthResponse,
    OrderCreateRequest,
    OrderResponse,
    OrderUpdateRequest,
    ProductResponse,
    SessionResponse,
)
from my_project.api.session_store import InMemorySessionStore
from my_project.application.session import SupportSession
from my_project.application.turn_processor import process_turn
from my_project.evaluation.report_reader import (
    DEFAULT_REPORT_PATH,
    EvaluationReportNotFoundError,
    InvalidEvaluationReportError,
    get_report_summary,
    load_latest_report,
)
from my_project.products.catalog import get_product, list_products
from my_project.services.customer_service import (
    CustomerConflictError,
    CustomerNotFoundError,
    CustomerService,
    CustomerValidationError,
    get_customer_service,
)


TurnProcessor = Callable[[SupportSession, str, str | None], str]

MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def _has_valid_image_signature(content_type: str, header: bytes) -> bool:
    if content_type == "image/png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return header.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    return False


def _save_temporary_image(image: UploadFile) -> str:
    """Validate and stream one upload to a generated temporary path."""
    suffix = IMAGE_TYPES.get(image.content_type or "")
    if suffix is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image type. Use PNG, JPEG, or WebP.",
        )

    path: str | None = None
    try:
        with NamedTemporaryFile(prefix="support-upload-", suffix=suffix, delete=False) as temp:
            path = temp.name
            size = 0
            header = b""
            while chunk := image.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail="Image exceeds the 10 MB size limit.",
                    )
                if len(header) < 12:
                    header = (header + chunk)[:12]
                temp.write(chunk)

        if size == 0 or not _has_valid_image_signature(image.content_type or "", header):
            raise HTTPException(
                status_code=400,
                detail="Uploaded file content does not match a supported image format.",
            )
        return path
    except BaseException:
        if path is not None:
            Path(path).unlink(missing_ok=True)
        raise


def create_app(
    session_store: InMemorySessionStore | None = None,
    turn_processor: TurnProcessor = process_turn,
    evaluation_report_path: str | Path = DEFAULT_REPORT_PATH,
    customer_service: CustomerService | None = None,
) -> FastAPI:
    """Create an API instance with explicit in-memory dependencies."""
    api = FastAPI(title="Support Agent API")
    api.state.session_store = session_store or InMemorySessionStore()
    api.state.turn_processor = turn_processor
    api.state.evaluation_report_path = Path(evaluation_report_path)
    api.state.customer_service = customer_service or get_customer_service()

    api.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173","http://127.0.0.1:5173",],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    def service_call(operation):
        try:
            return operation()
        except CustomerNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except CustomerConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except CustomerValidationError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    def order_response(order) -> dict:
        product = get_product(order.product_id)
        return {**order.__dict__, "product": product.__dict__}

    def customer_detail(service: CustomerService, customer_id: str) -> dict:
        customer = service.get_customer(customer_id)
        orders = service.list_orders_for_customer(customer_id)
        return {**customer.__dict__, "orders": [order_response(item) for item in orders]}

    @api.get("/admin/products", response_model=list[ProductResponse], tags=["Admin"])
    def admin_products() -> list[dict]:
        return [{**item.__dict__, "aliases": list(item.aliases)} for item in list_products()]

    @api.get("/admin/customers", response_model=list[CustomerResponse], tags=["Admin"])
    def admin_list_customers(request: Request) -> list:
        return request.app.state.customer_service.list_customers()

    @api.post("/admin/customers", response_model=CustomerResponse, tags=["Admin"])
    def admin_create_customer(payload: CustomerCreateRequest, request: Request):
        return service_call(lambda: request.app.state.customer_service.create_customer(
            payload.name, payload.phone_last4
        ))

    @api.get(
        "/admin/customers/{customer_id}", response_model=CustomerDetailResponse, tags=["Admin"]
    )
    def admin_get_customer(customer_id: str, request: Request):
        return service_call(lambda: customer_detail(
            request.app.state.customer_service, customer_id
        ))

    @api.patch(
        "/admin/customers/{customer_id}", response_model=CustomerResponse, tags=["Admin"]
    )
    def admin_update_customer(
        customer_id: str, payload: CustomerUpdateRequest, request: Request
    ):
        changes = payload.model_dump(exclude_unset=True)
        return service_call(lambda: request.app.state.customer_service.update_customer(
            customer_id, **changes
        ))

    @api.delete("/admin/customers/{customer_id}", status_code=204, tags=["Admin"])
    def admin_delete_customer(customer_id: str, request: Request) -> None:
        service_call(lambda: request.app.state.customer_service.delete_customer(customer_id))

    @api.get(
        "/admin/customers/{customer_id}/orders",
        response_model=list[OrderResponse],
        tags=["Admin"],
    )
    def admin_list_orders(customer_id: str, request: Request) -> list[dict]:
        orders = service_call(lambda: request.app.state.customer_service.list_orders_for_customer(
            customer_id
        ))
        return [order_response(item) for item in orders]

    @api.post(
        "/admin/customers/{customer_id}/orders", response_model=OrderResponse, tags=["Admin"]
    )
    def admin_create_order(
        customer_id: str, payload: OrderCreateRequest, request: Request
    ) -> dict:
        values = payload.model_dump(mode="json")
        order = service_call(lambda: request.app.state.customer_service.create_order(
            customer_id, **values
        ))
        return order_response(order)

    @api.patch("/admin/orders/{order_no}", response_model=OrderResponse, tags=["Admin"])
    def admin_update_order(order_no: str, payload: OrderUpdateRequest, request: Request) -> dict:
        changes = payload.model_dump(exclude_unset=True, mode="json")
        order = service_call(lambda: request.app.state.customer_service.update_order(
            order_no, **changes
        ))
        return order_response(order)

    @api.delete("/admin/orders/{order_no}", status_code=204, tags=["Admin"])
    def admin_delete_order(order_no: str, request: Request) -> None:
        service_call(lambda: request.app.state.customer_service.delete_order(order_no))

    def read_evaluation_report(request: Request) -> dict:
        try:
            return load_latest_report(request.app.state.evaluation_report_path)
        except EvaluationReportNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail="No evaluation report found. Run the evaluation CLI first.",
            ) from error
        except InvalidEvaluationReportError as error:
            raise HTTPException(
                status_code=500,
                detail="Evaluation report is invalid or unreadable.",
            ) from error

    @api.get("/debug/evaluation/latest", tags=["Evaluation"])
    def evaluation_latest(request: Request) -> dict:
        return read_evaluation_report(request)

    @api.get("/debug/evaluation/summary", tags=["Evaluation"])
    def evaluation_summary(request: Request) -> dict:
        report = read_evaluation_report(request)
        try:
            return get_report_summary(report)
        except InvalidEvaluationReportError as error:
            raise HTTPException(
                status_code=500,
                detail="Evaluation report is invalid or unreadable.",
            ) from error

    @api.post("/session", response_model=SessionResponse)
    def create_session(request: Request) -> SessionResponse:
        session_id = request.app.state.session_store.create_session()
        return SessionResponse(session_id=session_id)

    @api.post("/chat", response_model=ChatResponse, response_model_exclude_none=True)
    def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        session = request.app.state.session_store.get_session(payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Support session not found")

        reply = request.app.state.turn_processor(
            session=session,
            user_input=payload.message,
            image_path=None,
        )
        return ChatResponse(reply=reply, stage=session.state.stage, **session.presentation)

    @api.post("/chat/multimodal", response_model=ChatResponse, response_model_exclude_none=True)
    def chat_multimodal(
        request: Request,
        session_id: str = Form(...),
        message: str = Form(""),
        image: UploadFile = File(...),
    ) -> ChatResponse:
        session = request.app.state.session_store.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Support session not found")

        image_path: str | None = None
        try:
            image_path = _save_temporary_image(image)
            reply = request.app.state.turn_processor(
                session=session,
                user_input=message,
                image_path=image_path,
            )
            return ChatResponse(reply=reply, stage=session.state.stage, **session.presentation)
        finally:
            image.file.close()
            if image_path is not None:
                Path(image_path).unlink(missing_ok=True)

    return api


app = create_app()
