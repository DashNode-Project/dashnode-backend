# EP-13 — Factibilidad y balance de alcance (DashNode)

## ¿Se puede satisfacer el documento completo en una iteración?

**Respuesta corta:** el diseño DA-13-01..12 es coherente con el código actual (EP-10/11/12 en `develop`), pero la épica completa (17 puntos, 5 HU, jobs, rollups, corpus 150 frases, reconciliación I-04..I-07) es **demasiado amplia** para un solo sprint sin riesgo en calidad.

## Estado previo (develop)

| Activó | Estado |
|--------|--------|
| Asistente texto/voz, cuotas, chat | EP-10 ✅ |
| Análisis visual de issues, `ai_analyses` | EP-12 ✅ |
| Pestaña «Métricas de IA» | Shell `metricas-ia`, `implemented: false` |
| Registro `ai_interactions` | No existía |
| Trazas `log_ai_stage` | Solo logs, sin `interaction_id` en BD |

## Decisión de balance (v1 entregada en `feature/ep-13-metricas-valoracion-ia`)

| Área | v1 (esta rama) | v1.1+ |
|------|----------------|--------|
| HU 114 Registro | Lista, detalle, filtros, auditoría de acceso, alcance admin/gerente | Export PA-17, job purge 12 meses |
| HU 115 Panel | KPIs en vivo vía `AiMetricsService` | Rollups `ai_metrics_daily` |
| HU 116 Por usuario | Agregación mismo servicio | Columnas opcionales PA-21 |
| HU 117 Valoración | Upsert solicitante, asistente + análisis | — |
| HU 118 Asistente | Familia METRICS determinista + enlace panel | Corpus 150 frases, EXPLAIN con Gemini acotado |
| Jobs | `expires_at` persistido | Celery/cron rollups y retención |
| Invariantes I-04..I-07 | Tests de servicio I-01..I-03 | Reconciliación nocturna |

## Coherencia con RNF-ADE-02

Panel y asistente METRICS comparten **`AiMetricsService`** en backend; el frontend muestra las mismas cifras que devuelve la API.