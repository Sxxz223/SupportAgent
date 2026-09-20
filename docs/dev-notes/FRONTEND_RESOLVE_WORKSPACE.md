# Resolve workspace frontend

The customer chat route now uses one visual workspace with two explicit modes.

- **Live service** creates a backend session and treats the returned `stage` and `reply` as authoritative. Stage labels are a frontend presentation of the existing workflow. Suggested buttons only submit ordinary user messages. The frontend does not infer ownership, warranty, diagnosis, or resolution.
- **Demo experience** runs a deterministic local scenario. It demonstrates clickable answers, path insertion and shortening, unresolved replanning, and user confirmation from 99% to 100%. It does not call model APIs or create tickets.

The product picker imports `products/catalog.json`, so supported product names are not duplicated in frontend source. Switching modes or restarting clears the page-local transcript after confirmation. Failed live requests retain the pending request for a manual retry. Images are restricted to PNG, JPEG, or WebP up to 10 MB before upload.

## Credential protection

Provider credentials remain in the ignored root `.env` file and are read by backend providers only. The tracked `.env.example` must contain empty placeholders. Repository-local pre-commit and pre-push hooks call `scripts/check-secrets.mjs`, which checks staged or outgoing Git blobs and reports filenames and categories without printing detected values.

Activate the hooks once per checkout:

```bash
git config core.hooksPath .githooks
```

These checks are an additional guard. They do not replace revoking a credential immediately if it was disclosed outside the repository.
