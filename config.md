# Configuración operativa — EP-15 / EP-16

Claves en `system_configs` (sembradas por migración `027_ep15_16_cmd_devops`):

| Clave | Valor por defecto | Uso |
|---|---|---|
| `devops_sim_success_lint` | 0.92 | Probabilidad de éxito lint |
| `devops_sim_success_test` | 0.85 | Probabilidad de éxito test |
| `devops_sim_success_build` | 0.95 | Probabilidad de éxito build |
| `devops_sim_success_deploy` | 0.98 | Probabilidad de éxito deploy |
| `devops_sim_duration_lint_s` | 12 | Duración planeada lint |
| `devops_sim_duration_test_s` | 48 | Duración planeada test |
| `devops_sim_duration_build_s` | 30 | Duración planeada build |
| `devops_sim_duration_deploy_s` | 20 | Duración planeada deploy |
| `devops_manual_run_cooldown_s` | 300 | Enfriamiento entre disparos manuales |

La paleta de comandos no usa variables de entorno adicionales; el catálogo es código versionado (`cmd-v1.0.0`).