# Changelog — dashnode-backend

## [Unreleased] — EP-13 Métricas, valoración y registro de IA

### Added
- Registro unificado `ai_interactions` / `ai_interaction_steps` con fail-closed antes del proveedor.
- API `/api/v1/ai/metrics/*` y valoraciones `PUT /api/v1/ai/interactions/{id}/rating`.
- Vínculo `interaction_id` en análisis de issues (EP-12).
- Familia METRICS en el orquestador del asistente (cifras deterministas).

### Deferred (v1.1)
- Rollups `ai_metrics_daily`, jobs de retención y reconciliación nocturna.
- Trigger PG de inmutabilidad (sustituido por validación en aplicación).
- Exportación del registro y corpus completo HU 118.