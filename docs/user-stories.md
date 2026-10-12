# Historias de usuario implementadas — EP-01 Autenticación y sesiones

> Texto original de las 5 HU de la épica (idéntico en `dashnode-backend` y
> `dashnode-frontend`). Estado del lote: COMPLETED (2026-10-11).
> Cada repositorio documenta en `code-structure.md` e `implementation-report.md`
> solo su capa; `integration-report.md` es el mismo en ambos.

## Matriz de trazabilidad HU → código → pruebas → evidencia

| HU | Capacidad | Código principal | Pruebas | Evidencia |
|---|---|---|---|---|
| HU_DN_01_01 | Página de presentación | Solo frontend (el backend no participa; la ruta pública no consulta datos protegidos) | Ver repositorio frontend | `docs/integration-report.md` |
| HU_DN_01_02 | Registro de Gerente | `app/modules/auth/application/use_cases.py` (`RegisterManagerUseCase`), `app/modules/auth/domain/{rules,errors,messages}.py`, `app/modules/auth/api/routes.py` (`POST /api/v1/auth/register`), `app/shared/infrastructure/hasher.py` | `tests/application/test_register_manager_use_case.py`, `tests/api/test_register_api.py`, `tests/unit/test_auth_rules.py` (hypothesis), `tests/integration/test_postgres_schema_and_registration.py` | `docs/implementation-report.md` |
| HU_DN_01_03 | Inicio de sesión | `app/modules/auth/application/session_use_cases.py` (`LoginUseCase`), `app/modules/auth/infrastructure/{models,repositories,session_tokens}.py`, `migrations/versions/002_*.py`, `POST /api/v1/auth/login` | `tests/application/test_login_use_case.py`, `tests/api/test_login_api.py`, `tests/integration/test_postgres_login_sessions.py` | `docs/implementation-report.md` |
| HU_DN_01_04 | Cerrar sesión | `LogoutUseCase`, `POST /api/v1/auth/logout` | `tests/application/test_logout_use_case.py`, `tests/api/test_logout_api.py`, integración PostgreSQL | `docs/implementation-report.md` |
| HU_DN_01_05 | Conservar sesión al recargar | `AuthenticateSessionUseCase`, `app/orchestration/security.py`, `GET /api/v1/auth/session` | `tests/api/test_session_api.py`, `test_login_api.py::test_session_expires_exactly_8_hours_after_login` | `docs/implementation-report.md` |
| Transversal | Contrato de error, CSRF por Origin, cabeceras, salud, configuración segura, scripts | `app/orchestration/{error_handling,middleware}.py`, `app/config.py`, `scripts/` | `tests/api/test_platform_api.py`, `tests/unit/test_shared_infrastructure_foundation.py`, `tests/unit/test_scripts_and_seed.py` | `docs/implementation-report.md` |

### Cobertura de tareas técnicas de backend / seguridad / BD / QA

| Tarea | Resolución |
|---|---|
| TK_DN_01_02_1 (BD) | Tabla `users` (nombre, correo único, hash, rol, estado) — migración 001; tipo `UtcDateTime` |
| TK_DN_01_02_3 / 4 / 6 | `RegisterManagerUseCase`: validaciones en servidor, Argon2id con sal, rol forzado a Gerente, error técnico genérico |
| TK_DN_01_02_7 / 8 | Pruebas listadas arriba; endpoint documentado en `docs/api-auth.md` y OpenAPI (`/docs`) |
| TK_DN_01_03_1 (BD) | Migración 002: `sessions` (solo digest SHA-256 del token) y `login_attempts` |
| TK_DN_01_03_3 / 4 / 5 | `LoginUseCase`: sesión en servidor, 5 intentos/15 min por cuenta, mensajes genéricos y cuenta desactivada |
| TK_DN_01_03_8 | `test_login_use_case.py`, `test_login_api.py`, integración PostgreSQL (concurrencia) |
| TK_DN_01_04_2 / 5 | `LogoutUseCase` y pruebas de rechazo de la sesión previa |
| TK_DN_01_05_1 / 2 / 5 | Cookie HttpOnly (`Max-Age` = 8 h + retención), `GET /auth/session`, pruebas de expiración |

### Decisiones y supuestos (no definidos literalmente por las HU)

| Tema | Decisión |
|---|---|
| Sesión vs. JWT del arquetipo | Las HU exigen sesión revocable en servidor + cookie HttpOnly: se retiró el flujo JWT (y `pyjwt`). |
| Mensajes no redactados por las HU | `NOT_AUTHENTICATED`: «Debe iniciar sesión para continuar.»; nombre > 100: «El nombre completo no puede superar los 100 caracteres.»; campos vacíos en login reutilizan «Todos los campos obligatorios deben ser diligenciados.» |
| Cuenta desactivada | Solo se revela con contraseña correcta (evita enumeración de cuentas). |
| Intentos fallidos | Se registran antes de verificar (seguro bajo concurrencia); los intentos rechazados no prolongan el bloqueo; un login correcto reinicia el contador; también aplica a correos inexistentes. |
| Expiración | Absoluta a las 8 h desde el login (sin renovación). La cookie vive `SESSION_COOKIE_RETENTION_HOURS` más para poder responder «Su sesión ha expirado…». |
| Cierre de sesión | Idempotente: una sesión desconocida/expirada también termina en «Sesión cerrada correctamente.» y limpia la cookie. |
| Ramas Git | El repositorio documenta trunk-based, pero la instrucción explícita del propietario exige `develop` + rama de épica; se sigue la instrucción. |
| Fuera de alcance | Recuperación de contraseña (HU_DN_01_06), desactivación de usuarios (HU_DN_01_17), redirección HU_DN_01_08: solo se dejó configuración de correo preparada. |

---

## Texto original de las historias de usuario (literal)

# Mitad de la Épica 1: Autenticación y Sesiones (EP-01)

---

## HU_DN_01_01 — Visualizar la página de presentación del producto antes de iniciar sesión

* **Épica**: EP-01 Autenticación y sesiones (AUT)
* **MVP**: MVP 1
* **Sprint**: Sprint 1
* **Rol**: Yo como Visitante
* **Característica / Funcionalidad**: Visualizar la página de presentación del producto antes de iniciar sesión
* **Razón / Resultado**: para conocer DashNode y llegar al formulario de ingreso o de registro sin necesitar una cuenta
* **Estado de validación**: Lista
* **Observación**: RF-AUT-07 (Prioridad SRS: Media). Pendiente cerrado: P-18.
* **Estimación**: 2 Puntos de Historia (Fibonacci)
* **Justificación de estimación**: Página estática pública con dos accesos y un mensaje de fallo, sin lógica de negocio.
* **Prioridad MoSCoW**: Should have
* **Justificación de prioridad**: Prioridad SRS Media; aporta la entrada pública al flujo, pero el MVP funciona accediendo directamente al inicio de sesión.
* **Notas del analista**: Los destinos de los accesos dependen de HU_DN_01_03 y HU_DN_01_02 del mismo sprint.

### Criterios de Aceptación

1. **Dónde**: Pantalla inicial pública, accesible sin sesión; desde ella se llega al inicio de sesión y al registro de Gerente.
2. **Campos (controles de la página)**:
* 2.1 Botón 'Iniciar sesión': abre HU_DN_01_03.
* 2.2 Enlace 'Registrarme como Gerente': abre HU_DN_01_02.
* 2.3 Contenido descriptivo del producto: nombre DashNode, propuesta de valor en una frase y resumen de los módulos principales (proyectos, backlog y sprints, reuniones, documentación, issues y asistente de IA).


3. **Validación**: Sin sesión válida la página se muestra completa.
4. **Restricción**: La página no muestra ni solicita datos de proyectos, usuarios ni páginas protegidas.
5. **Éxito**: Al cargar, el visitante ve la presentación con los dos accesos.
6. **Fallo técnico**: Si la información no puede cargarse se muestra 'No fue posible cargar la información. Intente nuevamente.'

### Definition of Ready (DoR)

* HU con rol, funcionalidad y razón definidos.
* Criterios de aceptación completos y sin pendientes por aclarar.
* Mensajes de éxito y fallo definidos.
* Estimada por el equipo.
* Priorizada.
* Sin dependencias bloqueantes sin resolver.
* Mockup o diseño de Figma de la página de presentación disponible.
* Textos de propuesta de valor y resumen de módulos aprobados por el interesado (P-18).

### Definition of Done (DoD)

* Código en la rama de desarrollo con revisión por pares.
* Todos los criterios de aceptación verificados.
* Pruebas unitarias y de aceptación pasando.
* Validaciones repetidas en el servidor.
* Mensajes literales exactos a los del backlog.
* Accesibilidad básica (no depender solo del color, operable con teclado).
* Sin errores de lint.
* Documentación actualizada.
* Demo aprobada por el Product Owner.
* La ruta pública no realiza ninguna solicitud de datos protegidos.
* Los accesos abren HU_DN_01_03 y HU_DN_01_02.

### Tareas Técnicas

* **TK_DN_01_01_1**: Maquetar la página pública de presentación con nombre, propuesta de valor y resumen de módulos
* *Tipo*: Frontend
* *Cubre criterios*: 1, 2.3


* **TK_DN_01_01_2**: Implementar el botón 'Iniciar sesión' y el enlace 'Registrarme como Gerente' con su navegación
* *Tipo*: Frontend
* *Cubre criterios*: 2.1, 2.2, 5


* **TK_DN_01_01_3**: Configurar la ruta como pública sin solicitar ni renderizar datos protegidos
* *Tipo*: Seguridad
* *Cubre criterios*: 3, 4


* **TK_DN_01_01_4**: Mostrar 'No fue posible cargar la información. Intente nuevamente.' ante fallo de carga
* *Tipo*: Frontend
* *Cubre criterios*: 6


* **TK_DN_01_01_5**: Escribir pruebas de aceptación de carga sin sesión, accesos y ausencia de datos protegidos
* *Tipo*: QA
* *Cubre criterios*: 3, 4, 5, 6



---

## HU_DN_01_02 — Registrar mi cuenta en la plataforma con el rol Gerente

* **Épica**: EP-01 Autenticación y sesiones (AUT)
* **MVP**: MVP 1
* **Sprint**: Sprint 1
* **Rol**: Yo como Visitante
* **Característica / Funcionalidad**: Registrar mi cuenta en la plataforma con el rol Gerente
* **Razón / Resultado**: para obtener una cuenta de Gerente y comenzar a organizar proyectos y equipos sin depender de un Administrador
* **Estado de validación**: Lista
* **Observación**: RF-AUT-01, RN-AUT-01, RN-AUT-02 (Prioridad SRS: Alta). Regla de negocio del cliente: registro público exclusivo Visitante → Gerente. Conflicto interno del SRS resuelto con K-01. Pendientes cerrados: P-01, P-19.
* **Estimación**: 5 Puntos de Historia (Fibonacci)
* **Justificación de estimación**: Formulario con cuatro campos validados en cliente y servidor, hash de contraseña y regla de rol resistente a manipulación.
* **Prioridad MoSCoW**: Must have
* **Justificación de prioridad**: Prioridad SRS Alta y regla explícita del cliente; es la única vía para crear el primer Gerente que habilita el flujo extremo a extremo.

### Criterios de Aceptación

1. **Dónde**: Pantalla 'Registro de Gerente', accesible desde la página de presentación y desde el inicio de sesión mediante el enlace 'Registrarme como Gerente'.
2. **Campos (el formulario contiene)**:
* 2.1 Nombre completo: texto, obligatorio, longitud máxima 100 caracteres. Si está vacío se muestra 'El nombre completo es obligatorio.'
* 2.2 Correo electrónico: texto, obligatorio, formato xxx@xxx.xxx y único en el sistema. Si el formato no es válido: 'El correo electrónico ingresado no tiene un formato válido.'; si ya existe: 'Ya existe una cuenta registrada con este correo electrónico.'
* 2.3 Contraseña: obligatoria, oculta por defecto con botón de visualización, de 8 a 64 caracteres con al menos una letra y un número. Si no cumple: 'La contraseña no cumple los requisitos mínimos de seguridad.'
* 2.4 Confirmar contraseña: obligatoria, mismas restricciones del campo 2.3 y debe coincidir con él; si no: 'Las contraseñas no coinciden.'
* 2.5 El formulario no incluye selector de rol: el rol asignado es siempre Gerente.
* 2.6 Botón 'Registrarme': inhabilitado mientras exista un campo obligatorio vacío.
* 2.7 Botón 'Cancelar': regresa al inicio de sesión sin guardar.


3. **Validación**: Al presionar 'Registrarme' el servidor repite todas las validaciones; si falta algún campo obligatorio se muestra 'Todos los campos obligatorios deben ser diligenciados.'
4. **Restricción**: La contraseña se almacena solo como hash con sal (Argon2 o bcrypt) y nunca se devuelve en respuestas ni registros. Toda solicitud pública que intente crear un usuario con rol Desarrollador o Administrador (aunque se manipule la petición) se rechaza con 'El registro público solo está disponible para el rol Gerente.' y no crea cuenta.
5. **Éxito**: 'Su cuenta de Gerente ha sido registrada correctamente. Puede iniciar sesión.' y se redirige al inicio de sesión.
6. **Fallo técnico**: Ante un error no anticipado (caída del servicio o tiempo de espera agotado) se muestra 'No fue posible completar la operación. Intente nuevamente.' sin alterar datos.

### Definition of Ready (DoR)

* HU con rol, funcionalidad y razón definidos.
* Criterios de aceptación completos y sin pendientes por aclarar.
* Mensajes de éxito y fallo definidos.
* Estimada por el equipo.
* Priorizada.
* Sin dependencias bloqueantes sin resolver.
* Mockup o diseño de Figma del formulario de registro disponible.
* Esquema de BD de usuarios y roles definido.
* Algoritmo de hash (Argon2 o bcrypt) acordado por el equipo.

### Definition of Done (DoD)

* Código en la rama de desarrollo con revisión por pares.
* Todos los criterios de aceptación verificados.
* Pruebas unitarias y de aceptación pasando.
* Validaciones repetidas en el servidor.
* Mensajes literales exactos a los del backlog.
* Accesibilidad básica (no depender solo del color, operable con teclado).
* Sin errores de lint.
* Documentación actualizada.
* Demo aprobada por el Product Owner.
* Contraseña almacenada solo como hash con sal y ausente de respuestas y registros.
* Una solicitud manipulada con rol Desarrollador o Administrador es rechazada y no crea cuenta.
* Correo único verificado en el servidor.

### Tareas Técnicas

* **TK_DN_01_02_1**: Definir el modelo de usuario con nombre, correo único, hash de contraseña, rol y estado
* *Tipo*: BD
* *Cubre criterios*: 2.2, 2.5, 4


* **TK_DN_01_02_2**: Construir el formulario 'Registro de Gerente' con validaciones de cliente y botones 'Registrarme' y 'Cancelar'
* *Tipo*: Frontend
* *Cubre criterios*: 1, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7


* **TK_DN_01_02_3**: Implementar el endpoint de registro que repite en el servidor todas las validaciones de campos y unicidad
* *Tipo*: Backend
* *Cubre criterios*: 2.1, 2.2, 2.3, 2.4, 3


* **TK_DN_01_02_4**: Aplicar hash con sal (Argon2 o bcrypt) y forzar el rol Gerente rechazando cualquier otro rol enviado
* *Tipo*: Seguridad
* *Cubre criterios*: 4


* **TK_DN_01_02_5**: Mostrar el mensaje de éxito y redirigir al inicio de sesión
* *Tipo*: Frontend
* *Cubre criterios*: 5


* **TK_DN_01_02_6**: Manejar el error no anticipado mostrando 'No fue posible completar la operación. Intente nuevamente.' sin alterar datos
* *Tipo*: Backend
* *Cubre criterios*: 6


* **TK_DN_01_02_7**: Escribir pruebas unitarias y de aceptación, incluida la petición manipulada con rol Desarrollador o Administrador
* *Tipo*: QA
* *Cubre criterios*: 2, 3, 4, 5, 6


* **TK_DN_01_02_8**: Documentar el endpoint de registro y sus códigos de respuesta
* *Tipo*: Documentación
* *Cubre criterios*: 3, 4



---

## HU_DN_01_03 — Iniciar sesión con mi correo y contraseña

* **Épica**: EP-01 Autenticación y sesiones (AUT)
* **MVP**: MVP 1
* **Sprint**: Sprint 1
* **Rol**: Yo como Administrador, Gerente o Desarrollador
* **Característica / Funcionalidad**: Iniciar sesión con mi correo y contraseña
* **Razón / Resultado**: para acceder únicamente a las funciones y datos que corresponden a mi rol
* **Estado de validación**: Lista
* **Observación**: RF-AUT-02 (Prioridad SRS: Crítica); RN-USU-08. Consolidada para los tres roles (sin diferencia funcional). Límite de intentos adoptado como definitivo.
* **Estimación**: 5 Puntos de Historia (Fibonacci)
* **Justificación de estimación**: Autenticación con hash, sesión en servidor, limitación de intentos, cuenta desactivada y redirección por tres roles.
* **Prioridad MoSCoW**: Must have
* **Justificación de prioridad**: Prioridad SRS Crítica; toda la funcionalidad autenticada del MVP depende de ella.
* **Notas del analista**: Los usuarios desactivados provienen de HU_DN_01_17 del mismo sprint; para probar el criterio 6 se requiere un usuario desactivado de prueba.

### Criterios de Aceptación

1. **Dónde**: Pantalla 'Inicio de sesión', accesible desde la presentación y desde la redirección por falta de sesión.
2. **Campos (el formulario contiene)**:
* 2.1 Correo electrónico: texto, obligatorio, formato xxx@xxx.xxx. Si el formato no es válido: 'El correo electrónico ingresado no tiene un formato válido.'
* 2.2 Contraseña: obligatoria, oculta por defecto con botón de visualización.
* 2.3 Botón 'Iniciar sesión': inhabilitado mientras algún campo esté vacío.
* 2.4 Enlace '¿Olvidó su contraseña?': abre HU_DN_01_06.


3. **Validación**: Con credenciales válidas y cuenta activa se concede el acceso según el rol (Administrador, Gerente o Desarrollador).
4. **Restricción**: La contraseña se compara contra su hash y la sesión se crea y valida en el servidor. Se permiten máximo 5 intentos fallidos en 15 minutos por cuenta (RNF-SEG-06); el sexto se rechaza con 'Ha superado el número de intentos permitidos. Intente nuevamente más tarde.'
5. **Éxito**: El sistema dirige a la pantalla de inicio del rol del usuario.
6. **Fallo**: Correo inexistente o contraseña incorrecta muestran el mismo mensaje 'Credenciales no válidas. Verifique su correo y contraseña.'; con credenciales correctas y cuenta desactivada se rechaza con 'Su cuenta está desactivada. Contacte al Administrador.' y no se inicia sesión.
7. **Fallo técnico**: Ante un error no anticipado (caída del servicio o tiempo de espera agotado) se muestra 'No fue posible completar la operación. Intente nuevamente.' sin alterar datos.

### Definition of Ready (DoR)

* HU con rol, funcionalidad y razón definidos.
* Criterios de aceptación completos y sin pendientes por aclarar.
* Mensajes de éxito y fallo definidos.
* Estimada por el equipo.
* Priorizada.
* Sin dependencias bloqueantes sin resolver.
* Mockup o diseño de Figma del inicio de sesión disponible.
* Esquema de BD de usuarios definido (TK_DN_01_02_1).
* Pantalla de inicio por rol definida.
* Mecanismo de sesión en servidor acordado (cookie HttpOnly, RNF-SEG-09).

### Definition of Done (DoD)

* Código en la rama de desarrollo con revisión por pares.
* Todos los criterios de aceptación verificados.
* Pruebas unitarias y de aceptación pasando.
* Validaciones repetidas en el servidor.
* Mensajes literales exactos a los del backlog.
* Accesibilidad básica (no depender solo del color, operable con teclado).
* Sin errores de lint.
* Documentación actualizada.
* Demo aprobada por el Product Owner.
* Contraseña comparada solo contra su hash.
* Sesión creada y validada en el servidor.
* Sexto intento fallido en 15 minutos rechazado (RNF-SEG-06).
* Mismo mensaje para correo inexistente y contraseña incorrecta.
* Cuenta desactivada no inicia sesión.

### Tareas Técnicas

* **TK_DN_01_03_1**: Crear el almacenamiento de sesiones y del contador de intentos fallidos por cuenta
* *Tipo*: BD
* *Cubre criterios*: 4


* **TK_DN_01_03_2**: Construir el formulario 'Inicio de sesión' con validación de formato, botón inhabilitado y enlace '¿Olvidó su contraseña?'
* *Tipo*: Frontend
* *Cubre criterios*: 1, 2.1, 2.2, 2.3, 2.4


* **TK_DN_01_03_3**: Implementar el endpoint que compara la contraseña contra su hash y crea la sesión en el servidor
* *Tipo*: Backend
* *Cubre criterios*: 3, 4


* **TK_DN_01_03_4**: Limitar a 5 intentos fallidos en 15 minutos por cuenta con el mensaje de bloqueo
* *Tipo*: Seguridad
* *Cubre criterios*: 4


* **TK_DN_01_03_5**: Devolver el mensaje genérico de credenciales no válidas y rechazar cuentas desactivadas con su mensaje
* *Tipo*: Backend
* *Cubre criterios*: 6


* **TK_DN_01_03_6**: Redirigir a la pantalla de inicio correspondiente al rol del usuario
* *Tipo*: Frontend
* *Cubre criterios*: 5


* **TK_DN_01_03_7**: Mostrar 'No fue posible completar la operación. Intente nuevamente.' ante error no anticipado
* *Tipo*: Frontend
* *Cubre criterios*: 7


* **TK_DN_01_03_8**: Escribir pruebas de credenciales válidas por rol, inválidas, cuenta desactivada y sexto intento
* *Tipo*: QA
* *Cubre criterios*: 3, 4, 5, 6, 7



---

## HU_DN_01_04 — Cerrar mi sesión

* **Épica**: EP-01 Autenticación y sesiones (AUT)
* **MVP**: MVP 1
* **Sprint**: Sprint 1
* **Rol**: Yo como Administrador, Gerente o Desarrollador
* **Característica / Funcionalidad**: Cerrar mi sesión
* **Razón / Resultado**: para evitar que otra persona use mi cuenta en el mismo equipo
* **Estado de validación**: Lista
* **Observación**: RF-AUT-03 (Prioridad SRS: Crítica); RN-AUT-03.
* **Estimación**: 2 Puntos de Historia (Fibonacci)
* **Justificación de estimación**: Acción única sin formulario: invalidar sesión en servidor y limpiar cliente.
* **Prioridad MoSCoW**: Must have
* **Justificación de prioridad**: Prioridad SRS Crítica; sin cierre de sesión el acceso no es seguro.

### Criterios de Aceptación

1. **Dónde**: Opción 'Cerrar sesión' del menú de usuario, visible en todas las vistas autenticadas.
2. **Campos**: No aplica captura de datos; la acción no requiere formulario.
3. **Validación**: Al activar la opción se invalida la sesión en el servidor y se limpia la sesión del cliente.
4. **Restricción**: Tras cerrar sesión, cualquier solicitud con la sesión previa se rechaza y ningún dato protegido permanece visible.
5. **Éxito**: El usuario regresa al inicio de sesión y se muestra 'Sesión cerrada correctamente.'
6. **Fallo técnico**: Ante un error no anticipado (caída del servicio o tiempo de espera agotado) se muestra 'No fue posible completar la operación. Intente nuevamente.' sin alterar datos.

### Definition of Ready (DoR)

* HU con rol, funcionalidad y razón definidos.
* Criterios de aceptación completos y sin pendientes por aclarar.
* Mensajes de éxito y fallo definidos.
* Estimada por el equipo.
* Priorizada.
* Sin dependencias bloqueantes sin resolver.
* Mockup o diseño de Figma del menú de usuario disponible.
* HU_DN_01_03 terminada (existe sesión que cerrar).

### Definition of Done (DoD)

* Código en la rama de desarrollo con revisión por pares.
* Todos los criterios de aceptación verificados.
* Pruebas unitarias y de aceptación pasando.
* Validaciones repetidas en el servidor.
* Mensajes literales exactos a los del backlog.
* Accesibilidad básica (no depender solo del color, operable con teclado).
* Sin errores de lint.
* Documentación actualizada.
* Demo aprobada por el Product Owner.
* Tras cerrar sesión, una solicitud con la sesión previa es rechazada.
* Ningún dato protegido permanece visible tras el cierre.

### Tareas Técnicas

* **TK_DN_01_04_1**: Agregar la opción 'Cerrar sesión' al menú de usuario en todas las vistas autenticadas
* *Tipo*: Frontend
* *Cubre criterios*: 1, 2


* **TK_DN_01_04_2**: Implementar el endpoint que invalida la sesión en el servidor
* *Tipo*: Backend
* *Cubre criterios*: 3, 4


* **TK_DN_01_04_3**: Limpiar la sesión del cliente y redirigir al inicio de sesión mostrando 'Sesión cerrada correctamente.'
* *Tipo*: Frontend
* *Cubre criterios*: 3, 4, 5


* **TK_DN_01_04_4**: Mostrar 'No fue posible completar la operación. Intente nuevamente.' ante error no anticipado
* *Tipo*: Frontend
* *Cubre criterios*: 6


* **TK_DN_01_04_5**: Escribir pruebas que verifiquen el rechazo de solicitudes con la sesión previa
* *Tipo*: QA
* *Cubre criterios*: 4, 5



---

## HU_DN_01_05 — Conservar mi sesión activa al recargar el navegador

* **Épica**: EP-01 Autenticación y sesiones (AUT)
* **MVP**: MVP 1
* **Sprint**: Sprint 1
* **Rol**: Yo como Administrador, Gerente o Desarrollador
* **Característica / Funcionalidad**: Conservar mi sesión activa al recargar el navegador
* **Razón / Resultado**: para no repetir el ingreso de credenciales durante mi jornada de trabajo
* **Estado de validación**: Lista
* **Observación**: RF-AUT-06 (Prioridad SRS: Alta); RNF-SEG-09. Pendiente cerrado: P-20.
* **Estimación**: 3 Puntos de Historia (Fibonacci)
* **Justificación de estimación**: Configuración de cookie segura, expiración de 8 h y restauración de vista sin formulario.
* **Prioridad MoSCoW**: Must have
* **Justificación de prioridad**: Prioridad SRS Alta; condición técnica de la sesión de la que dependen todas las vistas autenticadas.

### Criterios de Aceptación

1. **Dónde**: Cualquier vista autenticada.
2. **Campos**: No aplica captura de datos; la acción no requiere formulario.
3. **Validación**: Al recargar con una sesión vigente el usuario permanece autenticado en la misma vista.
4. **Restricción**: La sesión termina solo al cerrar sesión o al expirar; el almacenamiento local del navegador no contiene contraseñas ni credenciales en claro y el token no es legible por scripts (cookie HttpOnly, RNF-SEG-09). Duración de la sesión: 8 horas desde el inicio de sesión; al expirar se redirige al inicio de sesión (HU_DN_01_08).
5. **Éxito**: Tras recargar, el usuario continúa autenticado sin volver a iniciar sesión.
6. **Fallo**: Si la sesión expiró se redirige al inicio de sesión con 'Su sesión ha expirado. Inicie sesión nuevamente.'; si la información no puede cargarse se muestra 'No fue posible cargar la información. Intente nuevamente.'

### Definition of Ready (DoR)

* HU con rol, funcionalidad y razón definidos.
* Criterios de aceptación completos y sin pendientes por aclarar.
* Mensajes de éxito y fallo definidos.
* Estimada por el equipo.
* Priorizada.
* Sin dependencias bloqueantes sin resolver.
* HU_DN_01_03 terminada (existe sesión en servidor).
* Coordinación con HU_DN_01_08 para la redirección al expirar.

### Definition of Done (DoD)

* Código en la rama de desarrollo con revisión por pares.
* Todos los criterios de aceptación verificados.
* Pruebas unitarias y de aceptación pasando.
* Validaciones repetidas en el servidor.
* Mensajes literales exactos a los del backlog.
* Accesibilidad básica (no depender solo del color, operable con teclado).
* Sin errores de lint.
* Documentación actualizada.
* Demo aprobada por el Product Owner.
* Token en cookie HttpOnly no legible por scripts (RNF-SEG-09).
* Almacenamiento local sin contraseñas ni credenciales en claro.
* Sesión expira a las 8 horas del inicio.

### Tareas Técnicas

* **TK_DN_01_05_1**: Configurar la cookie de sesión HttpOnly con expiración de 8 horas desde el inicio de sesión
* *Tipo*: Seguridad
* *Cubre criterios*: 4


* **TK_DN_01_05_2**: Implementar el endpoint que valida la sesión vigente al cargar cualquier vista
* *Tipo*: Backend
* *Cubre criterios*: 1, 3


* **TK_DN_01_05_3**: Restaurar el estado autenticado en la misma vista al recargar el navegador
* *Tipo*: Frontend
* *Cubre criterios*: 2, 3, 5


* **TK_DN_01_05_4**: Redirigir al inicio de sesión con el mensaje de sesión expirada y mostrar el mensaje de fallo de carga
* *Tipo*: Frontend
* *Cubre criterios*: 6


* **TK_DN_01_05_5**: Escribir pruebas de recarga con sesión vigente, sesión expirada y ausencia de credenciales en almacenamiento local
* *Tipo*: QA
* *Cubre criterios*: 3, 4, 5, 6

---