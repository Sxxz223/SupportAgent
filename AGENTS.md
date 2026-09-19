# Project conventions

This is a behavior-preserving modularization of the original customer-support demo.

## Running and imports

- Use `.venv/bin/python main.py` from this directory, or an absolute path to `main.py` from another directory.
- Package execution also works from the parent directory: `my_project/.venv/bin/python -m my_project.main`.
- Use project-relative imports inside application modules. The local `my_project.agents` package is NOT the third-party `agents` SDK.
- Do not add the project directory to `PYTHONPATH` for package execution; it shadows the SDK. The script entry point removes this conflict from its import search path.
- Configure `DEEPSEEK_API_KEY` and `DASHSCOPE_API_KEY` in the environment. Never commit credentials.
- Install dependencies from `requirements.txt`. The embedding model may need downloading on first use.
- Run offline checks with `.venv/bin/python -m unittest discover -s tests -v`.
- Run the local API from this directory with `.venv/bin/uvicorn api.app:app --reload`.
- Run the local web UI from `frontend/` with `npm run dev`; use `http://localhost:5173` so it matches the API CORS origin.

## Module ownership

- `schemas`: structured state and updates, without provider connections.
- `workflow`: deterministic stage, action, state merge and tool permission rules.
- `tools`: the three existing decorated business tool implementations (currently mock data).
- `agents`: prompts, context, extractor parsing and Agent construction; accept a supplied model.
- `rag`: Markdown chunking, MiniLM embeddings, cosine similarity and Top-K retrieval after filtering by the confirmed Catalog product namespace.
- `vision`: perception and image encoding only; Qwen receives an injected client. Keep Mock Vision.
- `providers`: provider client/model creation; retain current providers, endpoints and model names.
- `products`: the single supported-product catalog and identifier/alias resolution used by repositories and RAG.
- `repositories`: replaceable customer-asset and ticket persistence contracts plus explicit demo implementations.
- `repositories/sqlite_customer_repository.py`: SQLite customer/order CRUD and ownership reads; enables foreign keys and cascading order deletion.
- `services`: deterministic customer identity matching, Catalog-validated order/customer operations, warranty lookup, and ticket creation over injected repositories.
- `data/demo_customers.json`: demo identity-to-asset fixture only; production must use authenticated account IDs and a real data source.
- `data/support.db`: project-relative SQLite customer/order persistence, initialized and seeded idempotently by the default customer service.
- `application/session.py`: `SupportSession` owns persistent state, history and turn index; `TurnContext` contains transient values for one turn.
- `application/context.py`: `AppContext` exposes the current SupportSession to SDK tools as local runtime context; it is not prompt content.
- `application/events.py`: `RuntimeEvent` records only important fact-producing actions and compact execution metadata.
- `trace`: structured, bounded per-turn observability. `TurnTrace` snapshots execution facts, `TraceRecorder` records them without changing decisions, and `format_trace` provides a developer-readable view.
- `evaluation`: fixed scenarios, deterministic Trace evaluators, isolated-session Runner, terminal/JSON reports, and CLI. Unit tests inject deterministic turn functions; live CLI runs use the existing `process_turn()` unchanged.
- `application/turn_processor.py`: `process_turn(session, user_input, image_path=None)` orchestrates a single turn, updates `session.state` in place, records successful User/Assistant messages and returns the final response.
- `context/builder.py`: selects, deduplicates, source-labels and formats the only model-visible decision context.
- `api/session_store.py`: owns the in-memory UUID-to-SupportSession mapping for one API process.
- `api/app.py`: parses/formats HTTP, resolves sessions and delegates each chat request to process_turn; it contains no Agent business rules.
- `frontend/`: React/TypeScript/Vite text-chat client; it owns display messages and one page-lifetime backend session ID, never business State.
- `main.py`: create demo state/input, call `process_turn`, and print the final response.

## Behavior constraints

Do not change prompts, decision priorities, matching rules, stage/tool permissions, RAG ranking or provider selection during structural changes. State must remain in the main Agent context together with Vision, recommended action and retrieved knowledge.

Historical issues are recorded in `REFACTOR_REPORT.md`; subsequent changes are recorded in the `T5_*_REPORT.md` files. The user explicitly authorized fixing early action calculation, charging phrase matching and the Mock Vision description. Preserve these fixes. In each turn, merge text and optional vision updates before computing Stage, then retrieve knowledge, decide the action, select tools, build one controlled Model Context and run the support Agent. Keep current-turn VisionUpdate separate from historical visual facts in SupportState. Pass `AppContext(session)` to the Main Agent Runner so tools update the same SupportState, then recompute Stage. Never expose `create_ticket` when `ticket_id` already exists, and retain the tool's own idempotency guard. Do not serialize AppContext, the full Session, arbitrary Runtime Events, full History, vectors or image data into the prompt. Do not silently change other business rules.

Offline mocked tests do not establish real model quality or service availability. Clearly distinguish those checks from live API validation.

Turn traces live in `SupportSession.traces` and remain separate from business State, conversation History, and Runtime Events. Trace data must use snapshots and bounded summaries; never record secrets, image bytes, embedding vectors, full prompts, SDK request objects, local context objects, or chain of thought. Trace recording failures must not fail a support turn.

Product ownership may enter State only from explicit user input or a successful customer repository lookup. Demo user names are not authentication. Unknown demo users have no fallback product. Product-specific RAG chunks must match the confirmed product and may never serve as ownership evidence.
Unknown or unsupported products receive no product-specific RAG knowledge. Product definitions must come from `products/catalog.json`; do not duplicate supported-product lists in tools or prompts.
