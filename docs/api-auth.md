# API de autenticación y sesiones (EP-01)

Base: `/api/v1/auth`. Documentación interactiva (solo fuera de producción): `/docs`.

## Convenciones

- **Sesión**: cookie `dashnode_session` (`HttpOnly`, `SameSite=Lax`, `Secure` según `SESSION_COOKIE_SECURE`,
  `Path=/`, `Max-Age` = `SESSION_TTL_HOURS` + `SESSION_COOKIE_RETENTION_HOURS`). El token es opaco
  (256 bits); la BD solo guarda su SHA-256. Nunca viaja en el cuerpo ni se acepta por cabecera.
- **CSRF**: las peticiones `POST/PUT/PATCH/DELETE` con cabecera `Origin` fuera de `CORS_ORIGINS` se rechazan
  (`403 ORIGIN_NOT_ALLOWED`). El frontend debe usar `credentials: "include"`.
- **Contrato de error** (todas las respuestas no exitosas):

```json
{ "error": { "code": "CODIGO_ESTABLE", "message": "Texto literal de la HU", "fields": { "campo": "detalle" } } }
```

- Las respuestas bajo `/api/` llevan `Cache-Control: no-store`.

## POST /register — HU_DN_01_02 (público)

Cuerpo: `{ "name", "email", "password", "confirm_password" }` (el campo opcional `role` solo se acepta con el valor `manager`).

| Código HTTP | `error.code` | Mensaje |
|---|---|---|
| 201 | — | Cuerpo `{ "message": "Su cuenta de Gerente ha sido registrada correctamente. Puede iniciar sesión.", "user": {…} }` (sin hash ni cookie) |
| 400 | `NAME_REQUIRED` | El nombre completo es obligatorio. |
| 400 | `REQUIRED_FIELDS` | Todos los campos obligatorios deben ser diligenciados. |
| 400 | `EMAIL_INVALID` | El correo electrónico ingresado no tiene un formato válido. |
| 400 | `PASSWORD_WEAK` | La contraseña no cumple los requisitos mínimos de seguridad. |
| 400 | `PASSWORD_MISMATCH` | Las contraseñas no coinciden. |
| 400 | `NAME_TOO_LONG` | El nombre completo no puede superar los 100 caracteres. |
| 400 | `INVALID_REQUEST` | La solicitud no es válida. (tipos incorrectos / JSON mal formado) |
| 403 | `ROLE_NOT_ALLOWED` | El registro público solo está disponible para el rol Gerente. |
| 409 | `EMAIL_ALREADY_REGISTERED` | Ya existe una cuenta registrada con este correo electrónico. |
| 500 | `INTERNAL_ERROR` | No fue posible completar la operación. Intente nuevamente. |

Reglas: correo normalizado a minúsculas (unicidad insensible a mayúsculas, también bajo concurrencia);
contraseña 8–64 caracteres con letra y número; hash Argon2id con sal.

## POST /login — HU_DN_01_03 (público)

Cuerpo: `{ "email", "password" }`. Éxito `200`: `{ "user": {id,email,name,role,is_active,created_at}, "expires_at": "<ISO-8601 UTC>" }`
y cabecera `Set-Cookie` con la sesión. El frontend dirige según `user.role` (`admin`, `manager`, `developer`).

| Código HTTP | `error.code` | Mensaje |
|---|---|---|
| 400 | `EMAIL_INVALID` | El correo electrónico ingresado no tiene un formato válido. |
| 400 | `REQUIRED_FIELDS` | Todos los campos obligatorios deben ser diligenciados. |
| 401 | `INVALID_CREDENTIALS` | Credenciales no válidas. Verifique su correo y contraseña. (correo inexistente y contraseña incorrecta, idénticas) |
| 403 | `ACCOUNT_DISABLED` | Su cuenta está desactivada. Contacte al Administrador. (solo con contraseña correcta) |
| 429 | `LOGIN_ATTEMPTS_EXCEEDED` | Ha superado el número de intentos permitidos. Intente nuevamente más tarde. |
| 500 | `INTERNAL_ERROR` | No fue posible completar la operación. Intente nuevamente. |

Límite: 5 intentos fallidos en 15 minutos por cuenta; el sexto se rechaza (incluso con la contraseña correcta)
sin ampliar el bloqueo. Un inicio correcto reinicia el contador.

## POST /logout — HU_DN_01_04

Sin cuerpo. `200 { "message": "Sesión cerrada correctamente." }` y la cookie se elimina. Idempotente: sin sesión o con
una sesión caducada/revocada también responde 200. Tras el cierre, cualquier petición con la cookie previa recibe
`401 NOT_AUTHENTICATED`. Un fallo técnico responde `500 INTERNAL_ERROR` sin tocar la cookie.

## GET /session — HU_DN_01_05

Valida la cookie en el servidor. `200 { "user": {…}, "expires_at": "…" }`. No renueva la sesión.

| Código HTTP | `error.code` | Mensaje |
|---|---|---|
| 401 | `NOT_AUTHENTICATED` | Debe iniciar sesión para continuar. (sin cookie, token desconocido o revocado; se elimina la cookie) |
| 401 | `SESSION_EXPIRED` | Su sesión ha expirado. Inicie sesión nuevamente. (se elimina la cookie) |
| 403 | `ACCOUNT_DISABLED` | Su cuenta está desactivada. Contacte al Administrador. |

## Salud

- `GET /health`: liveness. `GET /health/ready`: comprueba la base de datos (`503` si no responde).
