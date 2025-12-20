# Repo Cleanup Plan

This codebase is cluttered with generated artifacts, backups, and overlapping configs. Here’s a concise plan to make it feel intentional and easy to onboard.

## Immediate hygiene (safe to do now)
- Stop tracking generated bundles: remove committed files under `extensions/vscode-aep/out/` and keep only source + current build target. Add the folder to `.gitignore` (done).
- Delete legacy backups and `*_backup`, `*-old`, `*-previous` files in `extensions/vscode-aep/src` and root (done).
- Drop stale, unused scripts/tests (e.g., old integration stubs) after verifying they’re not referenced in CI.

## Dev experience
- One source of truth for backend URL: use `aep.navi.backendUrl` in VS Code settings and surface it in the chat UI as “Backend: OK/Unreachable” so connection issues are obvious.
- Add a health script (`scripts/backend_health.sh`) to quickly verify `/api/navi/chat` responds with a small payload.
- Document the minimal dev flow: start backend (`start_backend_dev.sh`), start frontend (`npm run dev` in `frontend`), reload extension.

## Code quality & structure
- Run formatter/lint across `frontend/` and `extensions/vscode-aep/src/` and remove dead imports/components (old panel backups).
- Consolidate chat/clipboard handling: native copy/paste by default, optional VS Code mirror, no duplicated handlers.
- Cap chat history and persist per-workspace to avoid mixing contexts.

## Testing
- Add a smoke test that hits `/api/navi/chat` with a dummy message and asserts a 200 + JSON body.
- Add a tiny UI test to ensure the chat input accepts paste and Enter-to-send works.

## When cleaning, do not
- Revert user changes in `backend/` or migration files.
- Delete CI-referenced assets without replacing/redirecting.
