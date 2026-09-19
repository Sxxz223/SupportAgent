# T7.1 Turn Trace

## Structure

The new `trace/` package contains:

- `models.py`: `TurnTrace`, `VisionTrace`, `RetrievalChunkTrace`, `ToolCallTrace`, and `ErrorTrace`.
- `recorder.py`: safe State snapshots, bounded RAG parsing, fault-tolerant turn recording, tool-call recording, and `format_trace()`.
- `__init__.py`: the public trace API.

Each `SupportSession` owns an in-memory `traces` list. A turn appends its trace when it starts and completes it in `finally`, including failed turns. Trace storage remains separate from State, History, and Runtime Events.

## Recorded lifecycle

`process_turn()` records input and State before work, extraction output, optional Vision summary, State after perception, Stage, retrieval metadata, next action, allowed tools, context section names, Main Agent invocation and reply, Tool calls, newly produced Runtime Event types, final State, final Stage, duration, and safe failure information.

The decision and execution order is unchanged. The trace does not feed back into the model context or workflow.

## Data boundaries

- State snapshots contain only selected business fields and copy mutable lists.
- RAG records source, parsed score, and a preview capped at 180 characters.
- Vision records whether it was used, relevance, a bounded observation, and changed State fields.
- Tool records safe arguments, a bounded result summary, success, duration, and changed State fields.
- Errors record stage, exception type, and a bounded message with common token patterns redacted.
- Image paths and bytes, Base64, vectors, complete prompts, local context objects, model request objects, credentials, and tracebacks are not stored.

## Reading

Python callers can inspect `session.traces`. `format_trace(session.traces[-1])` returns a compact report with Input, State, Extraction, Vision, Workflow, RAG, Tools, Final State, Final Answer, Duration, and Error sections.

## Reliability

Recorder operations catch their own errors. Tool operations execute exactly once even if trace metadata cannot be captured. Trace construction failure falls back to the original turn behavior.

## Verification

Dedicated tests cover text turns, multiple independent traces, RAG metadata, Vision summaries, Tool State closure, ticket creation, no-tool turns, safe error traces, immutable snapshots, formatter output, and recorder failure isolation.
