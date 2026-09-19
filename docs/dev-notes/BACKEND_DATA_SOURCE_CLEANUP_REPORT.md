# Backend Data Source Cleanup

The former runtime Tool module unconditionally returned `legacy demo product (removed)`, set warranty to `active` with a fixed date, and returned a fixed successful ticket ID. Those runtime constants were removed.

Product and warranty data now flow through `CustomerService` and the `CustomerRepository` contract. The demo implementation reads only explicitly configured users from `data/demo_customers.json`; no unknown-user fallback exists. Ticket creation flows through `TicketService` and `SupportTicketRepository`, with a process-local demo implementation generating IDs returned by its repository.

Only successful lookups modify `SupportState`. Product events distinguish `product_lookup_succeeded`, `product_lookup_not_found`, and `product_lookup_skipped`. Warranty events likewise distinguish success and not-found outcomes.

The model prompt now states that ownership comes only from explicit user input or successful lookup. RAG is not ownership evidence. Knowledge chunks carry document-title product metadata, and nonmatching product documents are excluded after the existing loader/retrieval entry point is called.

Demo-only data remains in JSON, knowledge Markdown, tests, Evaluation fixtures, and test images. Future CRM, order, device-binding, or ticket-system integration replaces repository implementations rather than Tool or Agent business interfaces.
