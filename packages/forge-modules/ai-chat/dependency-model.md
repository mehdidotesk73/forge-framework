# Dependency Model — Forge Modules

This document describes the target dependency model for Forge modules
(using `ai-chat` as the reference) and what is already correct vs what
still needs to be built.

---

## The Four-PC Independence Rule

Every package must be independently installable and runnable:

| PC | What's installed | Must run |
|----|-----------------|----------|
| 1 | `forge-modules-ai-chat` only | standalone AI Chat service |
| 2 | `forge-suite` only | management UI for any Forge project |
| 3 | Both | module available in Suite UI |
| 4 | Clone a forge project that uses the module | full project with module |

---

## Python — already correct ✓

```
forge-framework          (no forge deps)
    ↑
forge-suite              depends on forge-framework only
    ↑ (separate, not nested)
forge-modules-ai-chat    depends on forge-framework only (NOT forge-suite)
```

`pip install forge-modules-ai-chat[anthropic]` on a blank PC installs:
`forge-modules-ai-chat` + `forge-framework` + `pyyaml` + `anthropic`.
No forge-suite required. ✓

`pip install forge-suite` on a blank PC installs:
`forge-suite` + `forge-framework`. No ai-chat required. ✓

No circular dependencies anywhere. ✓

**Rule to preserve:** A module's `pyproject.toml` must depend on
`forge-framework`, never on `forge-suite`. forge-suite is a distribution
vehicle, not a dependency.

---

## TypeScript — mostly correct, two gaps

### Current chain (correct)

```
@forge-suite/ts           (peer: react, react-dom, @tanstack/react-query)
    ↑ peerDep
@forge-suite/ai-chat      (peer: react, react-dom, @forge-suite/ts, @tanstack/react-query)
```

`@forge-suite/ai-chat` does **not** bundle `@forge-suite/ts` — it declares it
as a peer dep and excludes it from the lib build via `rollupOptions.external`.
This means the host only ever installs one copy of `@forge-suite/ts`,
regardless of how many modules are installed. ✓

**Rule to preserve:** Every module's `vite.config.ts` must list `react`,
`react-dom`, and `@forge-suite/ts` as rollup externals in library mode.
They must appear in `peerDependencies`, never in `dependencies`.

### Gap 1 — Standalone prod serving (PC 1 prod)

**Status:** Missing.

In dev, `npm run dev` in `apps/ai-chat-app/` works fine. In production
(PC 1 without forge-suite), there is no mechanism to serve the compiled
React app from the Python process, the way `forge-suite` serves
`webapp_dist/` via `forge-suite serve`.

**What needs to be built:**

1. Add a `build:app` script to `ai-chat-app/package.json`:
   ```json
   "build:app": "vite build --outDir webapp_dist"
   ```

2. Add `webapp_dist/` to `packages/forge-modules/ai-chat/` (gitignored,
   generated at release time by CI).

3. In `packages/forge-modules/ai-chat/pyproject.toml`, include the dist:
   ```toml
   [tool.hatch.build.targets.wheel.force-include]
   "webapp_dist" = "forge_modules_ai_chat/webapp_dist"
   ```

4. Add a `forge-modules-ai-chat serve` CLI command (similar to
   `forge-suite serve`) that starts uvicorn with the module's FastAPI
   app and serves `webapp_dist/` at `/`.

Until this is built, PC 1 standalone prod requires the user to run:
```bash
cd apps/ai-chat-app && npm run build
forge dev serve   # from packages/forge-modules/ai-chat/
```

### Gap 2 — Automated project injection (PC 4)

**Status:** Missing (tracked in `modules-wireup.md`).

When a user runs `forge module add ai-chat` in their project, the CLI
should automatically:

1. `pip install forge-modules-ai-chat[all]` in the project venv
2. Append `[[forge_modules]]` entry to `forge.toml`
3. Add `@forge-suite/ai-chat` to the project's `package.json` dependencies
4. Run `npm install` in each `[[apps]]` directory
5. Bootstrap the module's dataset UUIDs via `StorageEngine`

Without this, users must do steps 2–5 manually. The project can still be
cloned and run on PC 4 as long as the project's `package.json` and
`forge.toml` already contain the module entries.

---

## Windows build fix needed in `@forge-suite/ts`

`packages/forge-ts/package.json` has a Unix-only build script:
```json
"build": "vite build && cp src/forge.css dist/forge.css"
```

`cp` does not exist on Windows. Replace with the cross-platform node one-liner:
```json
"build": "vite build && node -e \"require('fs').copyFileSync('src/forge.css','dist/forge.css')\""
```

This is outside `packages/forge-modules/` so it is documented here rather
than changed directly.

---

## Summary

| Area | Status | Action needed |
|------|--------|---------------|
| Python dep chain | ✓ Correct | None |
| TS lib entry points (`main`/`module`/`exports`) | ✓ Fixed | Already corrected in package.json |
| TS peer dep declarations | ✓ Fixed | `@tanstack/react-query` added to peerDeps |
| TS lib externals | ✓ Correct | react + @forge-suite/ts excluded from bundle |
| Standalone prod serving (PC 1) | ✗ Missing | Build Gap 1 above |
| Automated project injection (PC 4) | ✗ Missing | Build `forge module add` CLI (wireup doc) |
| `@forge-suite/ts` Windows build | ✗ Missing | Fix `cp` in forge-ts/package.json |
