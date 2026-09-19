# T6.3 Web multimodal image upload

## Scope

T6.3 adds the Web-to-`image_path` adapter around the existing application. It does not change Vision, RAG, Workflow, provider, tool, or Agent behavior.

## API

- `POST /chat` remains the JSON text endpoint.
- `POST /chat/multimodal` accepts `session_id`, optional `message`, and one `image` as multipart form data.
- PNG, JPEG, and WebP are accepted up to 10 MB. Both the declared media type and file signature are checked.
- An accepted upload is streamed to an operating-system temporary file, passed to the existing `process_turn(session, user_input, image_path)`, and deleted in a `finally` block.
- The endpoint resolves the existing session before reading the upload, so an unknown ID returns 404 and never creates a hidden session.

## Frontend

- The API client sends text through `/chat` and an image through `/chat/multimodal`. The browser supplies the multipart boundary.
- `ChatInput` supports a single image, local preview, removal, text plus image, and image-only submission.
- User messages can render a local image URL. This URL is display-only and never represents backend business state.
- The page keeps one backend session ID for both text and multimodal turns.

## Verification

- Python: 40 tests passed, including upload validation, size rejection, temporary-file cleanup, session reuse, and mocked integration through Vision and Agent context.
- Frontend: 9 tests passed, including FormData construction, endpoint routing, preview removal, image-only submission, and clearing the selected image.
- Production build: `npm run build` passed.
- Live browser check: the existing legacy demo product (removed) image was previewed and sent with text. The real backend returned a response based on dirty charging contacts. A following text-only turn reused the session and explicitly treated the prior photo as historical evidence.

## Deferred items

The requested backlog remains unchanged: multiple images, drag and drop, compression, persistent storage, streaming, WebSocket, authentication, Redis, database storage, and production object storage.
