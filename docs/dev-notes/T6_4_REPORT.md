# T6.4 Demo frontend polish

## Scope

This change only updates the React frontend. Agent Core, Session, Workflow, RAG, Vision, tools, providers, and HTTP contracts remain unchanged.

## Presentation and interaction

- Assistant replies use `react-markdown` with `remark-breaks`. Raw HTML is skipped. Bold text, paragraphs, ordered and unordered lists, and line breaks render normally. User messages remain plain text.
- Image previews stay compact in the composer. Sent images preserve their aspect ratio with `object-fit: contain`; image-only and image-plus-text messages share the same user message container.
- The thinking state is a compact assistant-style status with three static dots. Inputs and sending remain locked while a request is active.
- Network and backend details are logged only in development tools. The visible interface shows a stable, friendly retry message.
- Workflow stage remains available in component state but is guarded by `DEBUG = false`, so internal stage and session data are hidden in demo mode.
- The textarea focuses when available, grows up to 144 px, then scrolls internally. Enter sends and Shift+Enter adds a line break.
- New messages, thinking state changes, and completed image loads scroll the conversation to its latest content. Header and composer remain outside the independently scrolling message area.

## Verification

- Frontend tests: 10 passed.
- Production build: passed (`184` modules transformed; JavaScript gzip size approximately `106.12 kB`).
- Browser checks passed for text chat, semantic Markdown rendering, compact image preview, image plus text, visible thinking state, locked duplicate submission, long reply scrolling, refresh to a new welcome state, and friendly offline UI.
- Live multimodal check passed with the existing legacy demo product (removed) test image and the existing Vision pipeline.

## Deferred work

Streaming, WebSocket, authentication, multi-session navigation, persistence, multiple image upload, drag and drop, voice, and production deployment remain outside this task.
