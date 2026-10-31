# Rendimiento — integración Gemini (EP-10)

## Cambios aplicados (después de migración SDK)

| Área | Antes | Después |
|------|--------|---------|
| API | REST `generateContent` manual | SDK `interactions.create` + `output_text` |
| Pensamiento | Default del modelo | `generation_config.thinking_level = "low"` |
| Tokens salida fallback | ~2048 | `max_output_tokens = 512` (respuestas cortas) |
| Continuación automática | Default SDK (multi-hop) | `automatic_continuation=False` |
| Reintentos HTTP SDK | Default (~5 intentos) | `attempts=2`, backoff acotado |
| Timeout solicitud | 180 s | 90 s (+ timeout HTTP ms en cliente) |
| Prompt fallback | Lista larga de proyectos | Hasta 8 nombres en una línea |
| Event loop | Voz async bloqueaba hilo | `run_in_threadpool` + pool `gemini-io` |
| Métricas | Ninguna | Log estructurado `assistant_request_metrics` |
| Streaming SSE | No | `generate_stream()` preparado; **UI pendiente** |
| `google-genai[aiohttp]` | No evaluado en prod | **Pendiente**: httpx actual suficiente para baja concurrencia |

## Métricas registradas

Cada consulta al orquestador emite un log INFO:

- `parse_ms`, `resolve_ms`, `postgres_ms`, `gemini_ms`, `gemini_calls`
- `gemini_ttft_ms` (cuando se use streaming con callback)
- `path` (`list_projects`, `gemini_fallback`, etc.)
- `total_ms` / `orchestrator_ms`

Filtrar en logs: `assistant_request_metrics`.

## Benchmark local

```bash
cd dashnode-backend
python scripts/benchmark_assistant_latency.py
```

El script mide rutas **deterministas** (sin red Gemini). Para comparar Gemini live:

```bash
set GEMINI_INTEGRATION=1
python scripts/diagnose_gemini.py
```

## Tabla comparativa (referencia)

Mediciones locales dependen de red y cuota. Valores orientativos tras optimización (determinista, SQLite/Postgres local, sin Gemini):

| Escenario | p50 (ms) | p95 (ms) | Llamadas Gemini |
|-----------|----------|----------|-----------------|
| «qué proyectos tengo» | 15–80 | 120 | 0 |
| «Cuántas HUs tiene X» | 20–100 | 150 | 0 |
| Fallback UNKNOWN | 800–4000* | 8000* | 1 |

\* Gemini: altamente variable; revisar `gemini_ms` en logs.

## Pendiente (sin sacrificar calidad)

1. Endpoint SSE `/ai/text-generate/stream` conectado al widget React.
2. Benchmark automatizado before/after en CI con mock de Gemini (percentiles en artefacto).
3. Evaluación A/B de `google-genai[aiohttp]` bajo carga concurrente (>10 req/s).

## Pruebas de rendimiento recomendadas

1. **Determinista**: 20 iteraciones «proyectos» → p50/p95 de `total_ms` en logs.
2. **Gemini**: 10 iteraciones consulta ambigua → contar `gemini_calls=1`, registrar errores quota.
3. **Concurrencia**: login + voz simultáneo → login debe responder < 2 s (no bloqueo).
