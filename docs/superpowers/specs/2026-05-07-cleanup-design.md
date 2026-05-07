# Runtime Cleanup Design

## Problem

The project has a mix of intentional defaults and hidden fallback behavior. Some of those paths are useful, but several runtime branches quietly recover from real failures by retrying, returning empty data, or swallowing exceptions. That makes the app harder to reason about and can hide broken integrations.

## Goal

Remove silent fallback/recovery paths and unused helper code while keeping required configuration defaults and explicit feature toggles. The app should fail loudly on real workflow errors, with clear messages and no hidden recovery. The resulting code should be direct, readable, and free of unnecessary try/catch blocks, nested if/else chains, and duplicate branching.

## Approaches

### 1. Surgical cleanup (recommended)

Remove only the fallback paths that hide failures in core workflows, keep required startup defaults, and trim dead helper code where it is no longer needed.

### 2. Strict fail-fast everywhere

Remove almost every fallback, including some resilience guards and UX placeholders. This is cleaner in theory, but it is riskier and more disruptive.

### 3. Dead-code pass only

Delete obvious unused code and leave runtime behavior mostly unchanged. Lowest risk, but it would not solve the hidden-failure problem.

## Chosen design

Use the surgical cleanup approach.

## Backend changes

### AI and media services

- Remove fallback keyword retrying in clip search.
- Replace silent empty-result recovery with explicit service errors when a required provider cannot return usable data.
- Keep deterministic processing helpers that are part of the core pipeline, such as media fit/trim logic, but do not let them hide real failures.
- Replace broad exception swallowing with specific errors that bubble up to the router layer.
- Keep try/catch blocks only where they add real value, such as translating a third-party failure into a domain error.

### Utility helpers

- Tighten serialization helpers so malformed persisted JSON does not silently degrade to empty lists.
- Make path conversion explicit and validation-driven instead of returning raw paths as a hidden fallback.

### Routers

- Keep routers thin and explicit: validate state early, call services, and convert service failures into HTTP errors with actionable messages.
- Remove duplicate defensive branches that only mask bad state instead of fixing it.

## Frontend changes

- Simplify the API client error path so failed responses always surface a clear error.
- Remove polling/error branches that silently swallow refresh failures.
- Trim redundant helper code in stage components where state can be handled directly.
- Replace console-only failure handling in keyword optimization with visible UI errors.
- Collapse unnecessary conditional branches where a direct expression is clearer.

## Non-goals

- No redesign of the overall video pipeline.
- No removal of required environment defaults.
- No change to the user-facing workflow stages unless needed to support the cleanup.

## Validation

- Run backend tests around clip search, voice generation, render execution, and malformed stored data.
- Run frontend lint/build checks after the cleanup.
- Confirm the app still creates projects, advances stages, and reports failures explicitly instead of silently recovering.
- Confirm the cleaned code reads as standard, maintainable production code rather than a collection of defensive workarounds.
