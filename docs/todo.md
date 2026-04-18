# Forge Framework — Todo List

Items are organized by layer. Priority: `[HIGH]`, `[MED]`, `[LOW]`.

---

## System / Cross-Cutting

- [ ] `[LOW]` **Authentication providers** — pluggable auth system supporting general login (email/password, OAuth2 social) and high-security work (MFA, API key rotation, session scoping). Should integrate at the dev server level and be declarable in `forge.toml` (e.g. `[auth] provider = "oauth2"`). Endpoint-level authorization decorators (e.g. `@requires_role("admin")`) should be built on top.

- [ ] `[LOW]` **Database provider integration** — abstract the storage backend behind a provider interface so projects can use external databases (PostgreSQL, MySQL, Snowflake, BigQuery) instead of, or alongside, DuckDB+Parquet. The `StorageEngine` already acts as the single access point; the provider interface should live there. Pipeline output, snapshot mutations, and run history must all work through whichever provider is configured.

- [ ] `[LOW]` **System-level notification sending API** — a cross-project notification bus that any Forge project can use to send email, Slack messages, webhooks, or SMS. Declarable in `forge.toml` (e.g. `[notifications] email_provider = "sendgrid"`). Exposable as a utility function in endpoint code (e.g. `send_notification(channel="email", to="...", subject="...", body="...")`). Should not couple to any specific provider — adapters per channel.

- [ ] `[MED]` **Version compatibility enforcement** — currently a warning; should be a hard error with a clear upgrade path message when Python and TypeScript package versions are mismatched.

- [ ] `[MED]` **`forge upgrade` dry-run output improvement** — show a diff of what schema changes each migration will make, not just the migration names.

- [ ] `[LOW]` **Audit log** — append-only record of every endpoint call (who called it, what params, what changed). Useful for compliance and debugging. Store in DuckDB `audit_log` table alongside `pipeline_runs`.

---

## Pipeline Layer

- [ ] `[MED]` **Pipeline retry policy** — declare `max_retries` and `retry_delay` in `forge.toml`. The scheduler should automatically retry failed scheduled runs before marking them as failed.

- [ ] `[MED]` **Partial output writes / checkpointing** — for long-running pipelines, allow writing interim results to a staging dataset before the final atomic commit, so progress isn't lost on transient failure.

- [ ] `[MED]` **Pipeline dependency ordering for `forge pipeline run --all`** — currently manual; should topologically sort from the DAG and run in dependency order.

- [ ] `[LOW]` **DAG visualization export** — `forge pipeline dag --format dot` to emit Graphviz `.dot` output for richer visualization in CI or docs.

- [ ] `[LOW]` **Pipeline run diffing** — `forge pipeline diff <name> <run_id_a> <run_id_b>` to compare two output dataset versions (schema changes, row count delta, sample rows).

- [ ] `[LOW]` **External trigger support** — fire a pipeline from an HTTP webhook or a message queue (Kafka, SQS) event in addition to cron.

---

## Model Layer

- [ ] `[MED]` **Relation integrity helpers** — utilities for validating that JSON key lists don't contain dangling IDs (keys that don't exist in the target dataset). Runnable via `forge model validate`.

- [ ] `[MED]` **Multi-field primary keys** — currently exactly one PK per model is enforced. Support composite PKs for models backed by datasets with natural compound keys.

- [ ] `[MED]` **Schema migration tooling** — when a pipeline adds a column to a dataset, `forge model build` picks it up, but snapshot models retain their old snapshot schema. Add `forge model migrate <Name>` to apply column additions/removals to existing snapshot datasets.

- [ ] `[LOW]` **Computed field declarations** — allow a model to declare fields computed at read time (pure Python, no storage) via a `@computed_field` decorator, distinct from computed column endpoints (which are batch, server-side, and for display only).

- [ ] `[LOW]` **Many-to-many relation support** — currently only one-to-many via JSON key lists. Support many-to-many via a junction dataset declared in the relation definition.

- [ ] `[LOW]` **Schema versioning in artifacts** — embed the Forge version and a content hash in `<Name>.schema.json` so the build system can detect whether a rebuild is actually needed.

---

## Control Layer

- [ ] `[HIGH]` **Param validation at call time** — currently params are declared but minimal runtime validation occurs. Add type coercion and required-field checks before calling the endpoint function, returning a structured 422 error on failure.

- [ ] `[MED]` **Streaming endpoint support** — allow an endpoint to return a generator / async generator for long-running operations, streamed as SSE or NDJSON to the client.

- [ ] `[MED]` **Endpoint-level rate limiting** — declare `rate_limit` in the `@action_endpoint` decorator (e.g. `"10/minute"`). Enforced at the FastAPI route level.

- [ ] `[MED]` **Background task endpoints** — an endpoint variant that enqueues work and returns a job ID immediately, with a status polling endpoint (`GET /api/jobs/{id}`).

- [ ] `[LOW]` **Endpoint deprecation annotation** — mark an endpoint as deprecated in its decorator; the server returns a `Deprecation` response header and logs a warning. Enables graceful API evolution.

- [ ] `[LOW]` **OpenAPI tag grouping** — automatically group generated OpenAPI docs by endpoint repo name for cleaner `/docs` navigation.

---

## View Layer

- [ ] `[HIGH]` **Pagination support in ObjectTable** — the widget currently renders whatever rows are in the `objectSet`. Add built-in pagination controls that call `load<Name>Set({ limit, offset })` automatically based on `objectSet.total`.

- [ ] `[MED]` **Column visibility controls** — allow users to show/hide columns in `ObjectTable` via a column picker UI component.

- [ ] `[MED]` **Editable cells in ObjectTable** — optional inline edit mode that calls an update endpoint on cell blur, without opening a modal.

- [ ] `[MED]` **DataGrid widget** — heavier-weight alternative to `ObjectTable` for large datasets: virtual scrolling, column resizing, frozen columns.

- [ ] `[MED]` **Form field validation** — client-side validation in `<Form>` before submission: required fields, type checks, custom regex. Declarable in the endpoint param definition.

- [ ] `[MED]` **ObjectTable CSV/Parquet export** — a download button that exports current visible rows (respecting filters and computed columns) as CSV or Parquet.

- [ ] `[LOW]` **Theming system** — CSS custom property overrides for brand colors, typography, and spacing, configurable at the `configureForge()` call site.

- [ ] `[LOW]` **Chart drill-down** — click a bar or point in `<Chart>` to filter a linked `<ObjectTable>` to the corresponding rows.

- [ ] `[LOW]` **Map widget** — render geolocated object sets on an interactive map (Leaflet or MapLibre), for projects with lat/lng fields.

- [ ] `[LOW]` **Toast / notification widget** — in-app notification display for endpoint call results, pipeline completion events, and real-time server-sent events.

- [ ] `[LOW]` **Real-time data via SSE** — `useForgeStream(objectType)` hook that subscribes to a server-sent event stream and updates the object set live as pipeline runs complete.
