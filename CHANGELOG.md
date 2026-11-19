# Changelog — dashnode-backend

## [Unreleased] — EP-15 Paleta de comandos y EP-16 DevOps Hub

### Added
- `GET /api/v1/commands` con catálogo `cmd-v1.0.0` filtrado por rol y membresía.
- DevOps Hub: `project_devops_profiles` / `project_devops_revisions` (migración `028`), APIs `GET/PUT .../devops` y `GET .../devops/revisions`.

### Removed
- Pipeline simulado, tablas `devops_pipeline_*`, claves `devops_sim_*` y endpoints `/devops/pipeline/*`.

## [Unreleased] — EP-14 Notificaciones

### Added
- Migración `026_ep14_notifications`: modelo transaccional, `event_key`, `read_at`, retención 180 días.
- `NotificationService` y catálogo cerrado de 8 eventos (DN-14-02).
- API `/api/v1/notifications` (lista con cursor, contador, lectura, abrir, borrado).
- Cableado transaccional en tareas, sprints, issues, reuniones y documentación.
- Decisiones PO (PA-01…PA-06): sin resubmit/reschedule/resolve en v1; retención 180 días; leer al navegar.

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