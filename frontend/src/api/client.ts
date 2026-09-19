import type { ChatResponse, SessionResponse } from "../types/chat";
import type {
  Customer,
  CustomerDetail,
  CustomerInput,
  Order,
  OrderInput,
  OrderUpdate,
  Product,
} from "../types/admin";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // Keep the status-based message when the server body is not JSON.
    }
    throw new Error(detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function listCustomers(): Promise<Customer[]> {
  return request<Customer[]>("/admin/customers", { method: "GET" });
}

export function getCustomer(customerId: string): Promise<CustomerDetail> {
  return request<CustomerDetail>(`/admin/customers/${encodeURIComponent(customerId)}`, {
    method: "GET",
  });
}

export function createCustomer(input: CustomerInput): Promise<Customer> {
  return request<Customer>("/admin/customers", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateCustomer(customerId: string, input: CustomerInput): Promise<Customer> {
  return request<Customer>(`/admin/customers/${encodeURIComponent(customerId)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteCustomer(customerId: string): Promise<void> {
  return request<void>(`/admin/customers/${encodeURIComponent(customerId)}`, {
    method: "DELETE",
  });
}

export function listProducts(): Promise<Product[]> {
  return request<Product[]>("/admin/products", { method: "GET" });
}

export function createOrder(customerId: string, input: OrderInput): Promise<Order> {
  return request<Order>(`/admin/customers/${encodeURIComponent(customerId)}/orders`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateOrder(orderNo: string, input: OrderUpdate): Promise<Order> {
  return request<Order>(`/admin/orders/${encodeURIComponent(orderNo)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteOrder(orderNo: string): Promise<void> {
  return request<void>(`/admin/orders/${encodeURIComponent(orderNo)}`, {
    method: "DELETE",
  });
}

export async function createSession(): Promise<string> {
  const response = await request<SessionResponse>("/session", {
    method: "POST",
  });
  return response.session_id;
}

export function sendMessage(
  sessionId: string,
  message: string,
): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      message,
    }),
  });
}

export function sendMultimodalMessage(
  sessionId: string,
  message: string,
  image: File,
): Promise<ChatResponse> {
  const body = new FormData();
  body.append("session_id", sessionId);
  body.append("message", message);
  body.append("image", image);

  return request<ChatResponse>("/chat/multimodal", {
    method: "POST",
    body,
  });
}
