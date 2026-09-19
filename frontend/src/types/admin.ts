export type Customer = {
  customer_id: string;
  name: string;
  phone_last4: string;
  created_at: string;
  updated_at: string;
};

export type Product = {
  product_id: string;
  display_name: string;
  model: string;
  category: string;
  rag_namespace: string;
  aliases: string[];
};

export type OrderStatus = "active" | "returned" | "replaced";

export type Order = {
  order_no: string;
  customer_id: string;
  product_id: string;
  purchase_date: string;
  warranty_until: string | null;
  status: OrderStatus;
  created_at: string;
  updated_at: string;
  product: Product;
};

export type CustomerDetail = Customer & { orders: Order[] };

export type CustomerInput = Pick<Customer, "name" | "phone_last4">;

export type OrderInput = Pick<
  Order,
  "order_no" | "product_id" | "purchase_date" | "warranty_until" | "status"
>;

export type OrderUpdate = Omit<OrderInput, "order_no">;
