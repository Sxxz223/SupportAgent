# Backend data sources

The local demo uses explicit replaceable data-access boundaries:

```text
Agent Tool
  -> CustomerService / TicketService
  -> CustomerRepository / SupportTicketRepository
  -> Demo JSON / process-local ticket store
```

`data/demo_customers.json` maps a small number of demo names to assets. A name is only a temporary lookup key because the project does not yet have authentication. Unknown names return no products and never fall back to a default model.

Production should replace `DemoCustomerRepository` with a `CustomerRepository` backed by an authenticated `user_id` or `account_id` and one of:

- CRM API
- order database
- device-binding service

`DemoTicketRepository` can likewise be replaced with an implementation backed by the production support system. The Agents SDK Tool wrappers and workflow-facing `SupportState` do not need to be rewritten when repositories change.

The Markdown knowledge base describes product behavior. It does not prove ownership. Current lightweight metadata filtering derives a product model from each document title and excludes product documents that do not match the confirmed State product.
