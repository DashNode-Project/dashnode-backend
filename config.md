# DashNode Backend — Configuration (EP-13 addendum)

## AI interaction registry (IAM)

No additional environment variables are required for EP-13 v1. Interaction rows set
`expires_at` at creation time (retention purge job deferred).

## Metrics API

| Endpoint | Roles |
|----------|--------|
| `GET /api/v1/ai/metrics/summary` | Admin, Manager |
| `GET /api/v1/ai/metrics/by-user` | Admin, Manager |
| `GET /api/v1/ai/metrics/interactions` | Admin, Manager |
| `GET /api/v1/ai/interactions/{id}` | Admin, Manager (scoped) |
| `PUT /api/v1/ai/interactions/{id}/rating` | Owner of interaction |

Query `period`: `today`, `7d`, `30d`, `month`, `custom` (requires `from` and `to` in UTC ISO).