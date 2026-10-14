# Contracts

Cross-repository contracts live here — interface agreements that repositories depend on across boundaries:

- API schemas (OpenAPI, protobuf, GraphQL)
- Message/event shapes
- Shared data contracts

Rules:

- A contract change is a breaking change until every consumer repository is updated.
- Each contract file declares its owner and its consumers.
- `verify-all` does not run contracts themselves; repositories verify against them in their own `scripts/verify`.

## Existing Contracts

### `openapi.json` — the invoice API

- **Owner:** `repositories/backend`. FastAPI generates it; `npm run api:types` (from the root) writes this file and then the frontend's types.
- **Consumers:** `repositories/frontend` (`src/api/schema.d.ts` is generated from it, and the typed client uses those types).
- **Checks:** a backend test fails when this file differs from what the API serves; a frontend test fails when `schema.d.ts` was not regenerated from it. Change the API, run `npm run api:types`, and commit the three together.
