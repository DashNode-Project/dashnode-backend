# Documento de Arquitectura de Software (SAD) — DashNode

> **Línea base descrita:** prototipo aprobado v1.0 (SPA sin backend, 2026-09-30). Donde el SRS v0.2 exige capacidades de servidor, este documento las registra como brecha (G-xx, sección 2.1) con su ruta de cierre; no las da por implementadas.

**Control de Cambios**

| Versión | Fecha | Autor / Rol | Descripción |
| --- | --- | --- | --- |
| 1.0.0 | 2026-10-09 | AI Software Architect | Primera versión. Consolida el SRS v0.2, el esquema lógico de datos y el documento base de arquitectura (Figma Make). Define las vistas de macro arquitectura, física, funcional y de despliegue, y registra las decisiones arquitectónicas (AD-xx) y las brechas SRS–arquitectura (G-xx). |

## 1. INTRODUCCIÓN

### 1.1 Propósito

**Objetivo del sistema.** DashNode es una plataforma web para gestionar proyectos de software con Scrum: backlog jerárquico (épica → historia → tarea), sprints con velocidad y burndown, tablero Kanban de seis estados, reuniones con cálculo de disponibilidad, base de conocimiento con aprobación, issues («Fix») con evidencia y análisis de IA que exige validación humana, y visualización DevOps. Tres roles (Administrador, Gerente, Desarrollador) operan con permisos distintos.

**Objetivo de este documento.** Describir la arquitectura que da soporte al SRS v0.2 y al prototipo aprobado, justificar las decisiones y servir de referencia para implementación, pruebas y evolución hacia un backend.

#### Decisiones arquitectónicas principales

| ID | Decisión | Origen | Justificación |
| --- | --- | --- | --- |
| AD-01 | SPA 100 % cliente, sin backend ni llamadas de red tras la carga | Documento base; RES-05 | Costo de infraestructura cero (RES-01) y despliegue trivial. La brecha con el SRS se gestiona en 2.1. |
| AD-02 | Monolito modular por features (components, context, hooks, pages, types, utils, data) | Documento base | Límites claros por módulo funcional; facilita RNF-MAN-04 y una futura extracción a servicios. |
| AD-03 | Estado con Context + useReducer, un contexto por dominio, sin Redux | Documento base | Sin dependencias adicionales; reducers puros y testeables; contextos acotados limitan re-renderizados. |
| AD-04 | Flujo unidireccional: acción → reducer → render + persistencia por efecto | Documento base | Cambios predecibles y trazables; punto único de escritura. |
| AD-05 | Navegación por estado (NavState), sin React Router | Documento base | Sin reglas de fallback en el servidor. Costo: sin deep links ni botón atrás (se revierte en la Fase 3 de migración). |
| AD-06 | Persistencia en localStorage (JSON), claves dashnode\_\* | Documento base | Único almacén disponible sin servidor. Límite de 5–10 MB. |
| AD-07 | Orquestación multi-contexto mediante el hook useAppActions | Documento base | Evita acoplar contextos entre sí en operaciones transversales (fix → tarea → notificación). |
| AD-08 | Autorización centralizada en una política can(usuario, acción, recurso) | Arquitecto (Propuesto) | Reemplaza comprobaciones de rol dispersas y es portable al servidor (RN-AUT-03, RNF-SEG-03). |
| AD-09 | Puertos y adaptadores: StorageAdapter y AIProvider | Arquitecto (Propuesto) | RNF-FLE-01. Permite pasar de localStorage a API REST sin tocar reducers (Fase 1 del documento base). |
| AD-10 | Transiciones de estado declarativas (tablas) para tarea, sprint, fix y aprobación | Arquitecto, derivadas del esquema | Reglas verificables con pruebas unitarias (RNF-MAN-01); sin condicionales duplicados. |
| AD-11 | Métricas derivadas (velocidad, burndown, progreso, KPIs de IA) como selectores puros | Arquitecto (Propuesto) | No se almacenan, por lo que no pueden quedar inconsistentes (RNF-ADE-02). |
| AD-12 | Error Boundary por módulo | Documento base | RNF-FIA-04: un fallo no se propaga a otros módulos. |
| AD-13 | Esquema de persistencia versionado y validación al hidratar | Arquitecto (Propuesto) | RNF-FIA-03: tolera datos locales corruptos u obsoletos sin caída. |
| AD-14 | Escrituras a localStorage coalescidas (debounce corto) con vaciado en pagehide | Arquitecto (Propuesto) | RNF-REN-08 (menos de 50 ms): evita serializar colecciones completas en cada cambio. |
| AD-15 | División de código por página (React.lazy y Suspense) | Arquitecto (Propuesto) | RNF-REN-05 y RNF-REN-06. El documento base solo declara render diferido. |
| AD-16 | Service Worker con precaché de assets (PWA) | Arquitecto (Propuesto) | Necesario para arrancar sin red en frío; el documento base solo garantiza operación offline después de la carga. |
| AD-17 | Hosting estático gratuito con CDN y CI/CD en GitHub Actions | Arquitecto; D-20 | RES-01 y RES-03; HTTPS incluido; previsualizaciones por pull request. |
| AD-18 | IA simulada tras el puerto AIProvider; un proveedor real exigirá un proxy en servidor | Documento base; RNF-SEG-05 | Las claves de servicios no pueden residir en el cliente. |

#### Patrones de diseño y justificación

| Patrón | Aplicación en DashNode | Justificación | Atributo favorecido |
| --- | --- | --- | --- |
| Reducer / flujo unidireccional (Flux) | Un reducer tipado por contexto (auth, task, fix, knowledge, etc.) | Transiciones puras y deterministas: misma acción y estado producen el mismo resultado, sin efectos ocultos. | Testeabilidad, mantenibilidad |
| Provider / Context | AppContextProvider y 10 contextos de dominio | Distribuye estado sin prop drilling; cada dominio se suscribe solo a lo que necesita. | Modularidad, rendimiento |
| Mediator / Facade | useAppActions | Un único punto coordina operaciones que tocan varios dominios; los reducers permanecen ignorantes unos de otros. | Mantenibilidad, adecuación funcional |
| Ports and Adapters | StorageAdapter, AIProvider | Aísla el dominio de la infraestructura; el cambio de proveedor no toca reglas de negocio. | Sustituibilidad, portabilidad |
| State Machine (tablas de transición) | Task, Sprint, Fix, aprobación de conocimiento | Hace explícitas las reglas del esquema y permite probarlas exhaustivamente. | Adecuación funcional, testeabilidad |
| Policy / Guard (RBAC) | AuthGuard en AppShell, can() | Autorización consistente y reutilizable en un futuro servidor. | Seguridad |
| Composite, Container / Presentational | Páginas → pestañas → tarjetas → átomos compartidos | Separa orquestación de datos y presentación; maximiza reutilización. | Reusabilidad, mantenibilidad |
| Observer | useNotifier, listener global de Ctrl+K | Reacciona a cambios de estado o eventos sin acoplar a los emisores. | Mantenibilidad |
| Error Boundary | Una por sección principal | Contiene fallos de renderizado y permite mostrar un mensaje local. | Fiabilidad |
| Memoización / selectores derivados | useMemo, useCallback | Evita recomputar listas filtradas y KPIs en cada render. | Rendimiento |
| Unión discriminada | NavState, acciones de reducers | El compilador exige tratar todos los casos; se eliminan estados imposibles. | Mantenibilidad, corrección |

#### Módulos y funcionalidades clave

| Módulo (código SRS) | Funcionalidades clave |
| --- | --- |
| Autenticación y sesiones (AUT) | Login, logout, sesión persistente, páginas de presentación, redirección de rutas protegidas |
| Usuarios y permisos (USU) | Creación por rol permitido, edición, perfil propio, desactivación lógica con liberación de tareas |
| Proyectos (PRO) | CRUD, estado, prioridad, stack, gerente responsable, membresía, espacio de trabajo por pestañas, indicadores de salud |
| Backlog y tareas (TAR) | Épicas, historias (puntos Fibonacci), tareas, etiquetas, prioridad, asignación, Mis tareas |
| Sprints (SPR) y Kanban (KAN) | Ciclo de vida del sprint, un solo sprint activo, velocidad, burndown, tablero de seis columnas con arrastre |
| Documentación (DOC) | Entradas con texto o enlace, cola de aprobación, visibilidad, anclado, búsqueda client-side |
| Disponibilidad (DIS) y Agendamiento (AGE) | Rejilla semanal por hora, intersección de horarios, reuniones, aceptación, cancelación, acta, Google Calendar |
| Issues (ISS), IA por imagen/video (IAI) | Fix con evidencia, vínculo a tarea (estado Corrección), análisis de IA con validación humana |
| IA por voz (IAV) y métricas (IAM) | Widget flotante, contexto del proyecto, registro de interacciones, valoración 1–5, métricas |
| Notificaciones (NOT) y paleta (CMD) | Bandeja con contador y enlaces; búsqueda y ejecución por teclado filtrada por rol |
| DevOps (DVO) y Dashboard | Pipeline, historial, puertas de calidad, Git Flow; KPIs por rol |

#### Atributos de calidad

**Observables** (se miden ejecutando el sistema):

- **Rendimiento:** carga inicial menor de 3 s en 4G (RNF-REN-05); interactivo en menos de 2 s (REN-06); reflejo de cambios de UI en menos de 100 ms (REN-07); lecturas y escrituras en localStorage en menos de 50 ms (REN-08); paleta de comandos en menos de 50 ms por tecla (REN-09); cálculo de horarios en 3 s p95 con 20 participantes (REN-01).
- **Seguridad:** control de acceso por rol, membresía y asignación; escape de contenido de usuario y de IA contra XSS (SEG-10); sin secretos ni contraseñas en claro. En la línea base la autorización es solo de cliente (brechas G-01 a G-03).
- **Disponibilidad y fiabilidad:** operación sin red después de la carga; Error Boundary por módulo (FIA-04); recuperación ante datos locales corruptos (FIA-03); degradación de IA ante cuota agotada (RN-IAG-02).
- **Usabilidad y accesibilidad:** WCAG 2.2 AA (INT-01), operación por teclado (INT-06), estados de carga, vacío, éxito y error (INT-03), acciones principales en 3 clics (INT-05).
- **Compatibilidad:** Chrome, Edge, Firefox y Safari en sus dos últimas versiones estables; piso Chrome 120, Firefox 120, Safari 17 (COM-01).
- **Adecuación funcional:** exactitud en horarios, velocidad, burndown y métricas de IA (ADE-01, ADE-02).
- **Capacidad:** 5–10 MB de almacenamiento; diseñado para menos de 100 proyectos y menos de 1000 tareas.

**No observables** (propiedades del código y del proceso):

- **Mantenibilidad y analizabilidad:** 100 % TypeScript, sin `any` (ESLint), componentes de hasta 300 líneas, JSDoc en componentes compartidos (MAN-02 a MAN-05).
- **Testeabilidad:** reducers y utilidades puras; cobertura de líneas de al menos 70 % en autorización y reglas (MAN-01).
- **Modularidad y reusabilidad:** organización por features y biblioteca de componentes compartidos sin lógica de dominio.
- **Sustituibilidad y portabilidad:** puertos para persistencia e IA (FLE-01); ruta de migración por fases a backend.
- **Evolucionabilidad:** esquema lógico relacional ya definido para migrar a PostgreSQL o Supabase.

### 1.2 Alcance

| Dentro del alcance (qué hace) | Fuera del alcance (qué no hace) |
| --- | --- |
| Autenticación por correo y contraseña, sesión persistente y guardas por rol | Aprovisionamiento real de cuentas y correos de activación o restablecimiento (requieren servidor) |
| Gestión de usuarios, proyectos, miembros y espacio de trabajo por pestañas | Autorización en servidor, limitación de intentos de login, hash con sal de contraseñas |
| Backlog, sprints, Kanban, Mis tareas y métricas del proyecto | Colaboración en tiempo real y sincronización entre dispositivos o pestañas |
| Documentación con aprobación, issues con evidencia, asistente de IA simulado con registro y valoración | IA real en la línea base; la IA nunca ejecuta ni verifica correcciones |
| Disponibilidad, cálculo de horarios, reuniones y apertura de Google Calendar por acción del usuario | Videollamadas propias, modificar calendarios externos sin autorización, SMS y correo de notificaciones |
| Notificaciones internas, paleta de comandos (Ctrl+K) y visualización DevOps simulada | Ejecutar pipelines reales, almacenar archivos de documentación, app móvil nativa, facturación, deep links y botón atrás |

La persistencia es local al navegador y al origen: los datos no se comparten entre personas ni entre dispositivos.

### 1.3 Definiciones, siglas y abreviaturas

| Término | Definición |
| --- | --- |
| SPA | Aplicación web de una sola página; toda la lógica corre en el navegador |
| SAD / DAS | Documento de Arquitectura de Software |
| AD / G | Decisión arquitectónica / brecha entre el SRS y la arquitectura vigente |
| Reducer | Función pura (estado, acción) → nuevo estado |
| Context | Mecanismo de React para compartir estado en el árbol de componentes |
| NavState | Unión discriminada que representa la página y pestaña actuales |
| Feature slice | Agrupación de código por capacidad funcional |
| localStorage | Almacén clave-valor síncrono del navegador, por origen, solo cadenas |
| Seed | Datos de demostración que inicializan el sistema cuando no hay datos guardados |
| Hidratación | Lectura del almacenamiento para construir el estado inicial |
| RBAC | Control de acceso basado en roles |
| Fix / Issue | Registro de defecto con evidencia, análisis de IA y resolución |
| Burndown / Velocidad | Puntos restantes del sprint por día / puntos completados por sprint |
| Quality gate | Criterio medible del pipeline (cobertura, puntaje de lint) |
| Git Flow | Modelo de ramas main, develop, feature, release y hotfix |
| Puerto / Adaptador | Interfaz del dominio / implementación concreta que la satisface |
| Service Worker / PWA | Script de red del navegador que cachea assets y habilita el arranque offline |
| CSP | Política de seguridad de contenido; restringe orígenes de scripts y recursos |
| HMR | Recarga de módulos en caliente del servidor de desarrollo de Vite |
| Code splitting | División del bundle en fragmentos cargados bajo demanda |
| XSS | Inyección de scripts mediante contenido no escapado |
| TTI | Tiempo hasta que la aplicación es interactiva |
| CI/CD | Integración y despliegue continuos |

### 1.4 Referencias

| ID | Documento | Versión / fecha | Uso en este SAD |
| --- | --- | --- | --- |
| REF-01 | 20261008\_SRS\_Requisitos\_de\_Software\_DN (SRS) | v0.2, 2026-10-09 | Fuente de mayor prioridad: reglas de negocio (RN), requisitos funcionales (RF) y no funcionales (RNF), permisos, restricciones y decisiones pendientes (D-xx) |
| REF-02 | database\_schema.md (esquema de base de datos) | Sin versión declarada | 21 entidades lógicas, reglas de integridad, flujos de estado y claves de localStorage |
| REF-03 | architecture\_document.md (documento base, Figma Make) | v1.0, 2026-09-30 | Stack, estilo, árbol de componentes, estado, navegación, persistencia y ruta de migración. Prevalece sobre el SRS en el stack técnico |
| REF-04 | ISO/IEC 25010:2023 | — | Clasificación de atributos de calidad |
| REF-05 | IEEE 1471 / ISO/IEC 42010 | — | Estructura del documento por vistas |

Criterio de precedencia: ante conflicto entre insumos prevalece el SRS en comportamiento y el documento base en tecnología. Los conflictos detectados se listan en 2.1. «(Propuesto)» indica una decisión del arquitecto que no figura en los insumos.

### 1.5 Vista Global y Stack Tecnológico

```
+----------------------------- Navegador (Chrome / Edge / Firefox / Safari) -----------------------------+
|  PRESENTACIÓN    React 19 · Tailwind v4 · pages · features (pestañas) · componentes compartidos · overlays |
|  APLICACIÓN      10 contextos + reducers · useAppActions · NavState · selectores derivados · can()       |
|  DOMINIO         tipos TypeScript · reglas de negocio · tablas de transición · utilidades puras          |
|  INFRAESTRUCTURA StorageAdapter (localStorage) · AIProvider (simulado) · reloj / generador de ids        |
+------------------+-----------------------------------------------------------+---------------------------+
                   | carga inicial (HTTPS, archivos estáticos)                 | salida por acción del usuario
          Hosting estático + CDN                                      Google Calendar (URL) · enlaces externos
```

| Capa | Tecnología | Justificación |
| --- | --- | --- |
| Frontend: UI | React 19 (componentes funcionales y hooks) | Modelo declarativo, ecosistema amplio, base ya aprobada en el prototipo (RES-04) |
| Frontend: lenguaje | TypeScript 5.7 | Tipado estricto; exigido por RNF-MAN-02 y RNF-MAN-03 (sin `any`) |
| Frontend: estilos | Tailwind CSS v4 (sin archivo de configuración) | Utilidades atómicas, CSS generado en build y sin runtime; coherente con el sistema de diseño DD-01 a DD-03 |
| Frontend: iconos | lucide-react | Tree-shaking por importación nombrada; iconografía profesional sin emojis (DD-02) |
| Frontend: build | Vite 8 | Servidor de desarrollo con HMR, empaquetado optimizado y división de código |
| Estado | useReducer + Context | AD-03 |
| Backend | Ninguno. Autenticación, IA y pipeline son servicios simulados dentro del cliente | AD-01, AD-18 |
| Base de datos | localStorage con JSON; modelo lógico relacional de 21 entidades documentado para migrar a PostgreSQL o Supabase | AD-06; el esquema evita rediseñar al migrar |
| Calidad (Propuesto) | ESLint con regla que prohíbe `any`; Vitest y Testing Library para reducers, reglas y componentes | Vitest comparte la configuración de Vite; cubre RNF-MAN-01 y RNF-MAN-03 |
| Infraestructura | Hosting estático con CDN y HTTPS (Cloudflare Pages o GitHub Pages) y GitHub Actions para CI/CD | AD-17; cuotas gratuitas por verificar al decidir (R-01, D-20) |

## 2. MACRO ARQUITECTURA

### 2.1 Metas y Restricciones Arquitectónicas

**Metas**

- Entregar el prototipo aprobado completo como SPA funcional, sin infraestructura propia.
- Mantener el dominio desacoplado de la infraestructura para migrar a un backend sin reescribir reducers ni interfaz (AD-09).
- Cumplir en el cliente los RNF medibles: rendimiento, accesibilidad y mantenibilidad.
- Hacer explícita cada brecha entre el SRS y la línea base, con su ruta de cierre.

**Restricciones**

| ID | Categoría | Restricción | Fuente | Implicación arquitectónica |
| --- | --- | --- | --- | --- |
| RA-01 | Técnica | Sin backend y sin llamadas de red tras la carga inicial | Documento base; RES-05 | Lógica, validación y autorización corren en el cliente |
| RA-02 | Técnica | localStorage: 5–10 MB según navegador, síncrono, solo cadenas, aislado por origen | Documento base | Serialización JSON; sin consultas ni transacciones; capacidad acotada (sección 3.3) |
| RA-03 | Técnica | Stack fijo: React 19, TypeScript 5.7, Tailwind v4, Vite 8 | Documento base; RES-04 | No se incorporan librerías de estado ni de enrutado |
| RA-04 | Técnica | Navegación por estado, sin URL por vista | Documento base | Sin deep links, historial ni marcadores (limitación conocida) |
| RA-05 | Técnica | Chrome 120+, Firefox 120+, Safari 17+; 1280 a 1920 px, mínimo 1280×720 | S-08, S-09, RNF-COM-01, RNF-INT-02 | Sin diseño móvil mientras D-26 siga abierta |
| RA-06 | Negocio | Sin presupuesto: solo capas gratuitas | RES-01 a RES-03 | Hosting y CI gratuitos; IA y voz acotadas por cuota (RN-IAG-02) |
| RA-07 | Negocio | La IA solo recomienda; un Administrador o Gerente valida antes de actuar | RN-IAG-03, RN-IAI-01 | Aviso visible y validación humana obligatoria; ninguna acción automática |
| RA-08 | Negocio | El audio nunca es permanente ni se almacena | RN-IAV-01, RN-IAV-02 | El audio vive en memoria y se descarta tras procesarse |
| RA-09 | Negocio | Mínimo privilegio según la matriz de permisos 7.2 | SRS | Autorización por rol, membresía y asignación mediante can() |
| RA-10 | Tiempo | Línea base posterior a MVP3 ya operativa; migración estimada en fases: 3 meses (API y autenticación), 1 mes (tiempo real), 2 semanas (URL), 1 mes (IA real) | Documento base | Definir puertos ahora para no rehacer trabajo (R-09) |
| RA-11 | Infraestructura | Solo hosting estático; ningún secreto en el cliente | RNF-SEG-05 | Las variables VITE\_\* son públicas: nunca contienen claves |
| RA-12 | Infraestructura | Los datos pertenecen al origen y navegador; cambiar de dominio o puerto muestra un almacén vacío | Navegador | Cada entorno tiene su propio conjunto de datos (sección 5.2) |
| RA-13 | Calidad | Sin `any`, componentes de hasta 300 líneas, JSDoc, cobertura mínima del 70 % en reglas | RNF-MAN-01 a MAN-05 | Reglas de ESLint y verificación automática en CI |

**Conciliación SRS ↔ arquitectura (brechas y conflictos entre insumos)**

| ID | Requisito o conflicto | Estado en la línea base | Resolución o ruta de cierre |
| --- | --- | --- | --- |
| G-01 | Autorización en servidor (RN-AUT-03, RF-AUT-05, RNF-SEG-03) | Solo guardas de cliente; quien edite localStorage puede alterar su rol | AD-08: la política can() se escribe una vez y se reutiliza en el servidor (Fase 1) |
| G-02 | Contraseñas con hash y sal (RNF-SEG-01, RNF-SEG-09) | El esquema guarda password\_hash simulado, en texto plano en localStorage | Solo credenciales de demostración; no cargar credenciales reales hasta la Fase 1 (hash Argon2 o bcrypt en servidor) |
| G-03 | Sesión no legible por scripts (RNF-SEG-09) | dashnode\_current\_user almacena el objeto de usuario completo | Guardar solo id de sesión y expiración; cookie HttpOnly en Fase 1 |
| G-04 | Evidencias validadas en servidor y accesibles solo a miembros (RF-ISS-02, RNF-SEG-08) | Contenido como URL o base64 dentro de localStorage; validación solo en cliente | Límite configurable por archivo (sección 3.3); almacenamiento de objetos en Fase 1 |
| G-05 | IA real en capa gratuita y secretos solo en servidor (RN-IAG-01, RNF-SEG-05) | Respuestas simuladas con temporizador; el modelo claude-3-5-sonnet es solo un valor simulado | Puerto AIProvider; voz a texto en el navegador sin secretos; texto e imagen mediante proxy en Fase 4 |
| G-06 | Enlaces de activación y restablecimiento (RF-AUT-04, RF-AUT-09, RNF-SEG-02) | No existe servicio de correo | Credencial temporal definida por el Administrador (opción de D-03) en modo demostración; enlaces reales en Fase 1 |
| G-07 | Límite de intentos de inicio de sesión (RNF-SEG-06) | No es aplicable de forma segura en el cliente | Fase 1 |
| G-08 | Desactivación atómica de usuario (RNF-FIA-02) | Un único dispatch y una escritura en lote; no es atómico si la pestaña se cierra a mitad de escritura | AD-13 y AD-14 detectan estados parciales al hidratar; transacción real en base de datos |
| G-09 | Recuperación con datos del servidor (RNF-FIA-03) | Solo puede descartar datos corruptos y volver al seed, con pérdida de datos | AD-13 más exportación e importación de respaldo en JSON (Propuesto); sincronización en Fase 1 |
| G-10 | Pestañas del proyecto (RF-PRO-07): Resumen, Backlog, Sprints, Kanban, Reuniones, Issues, Conocimiento, DevOps, Métricas de IA | El documento base declara además Team, Docs y Metrics y usa los nombres Fixes y Knowledge | Se conserva la lista del SRS; Fixes equivale a Issues y Knowledge a Conocimiento; confirmar las pestañas extra con producto |
| G-11 | Registro público: RN-AUT-01 y RF-AUT-01 lo permiten para Gerente; D-01 y la matriz 7.2 dicen que no existe | El documento base solo tiene LandingPage y LoginPage | Se adopta «sin registro público» hasta que producto resuelva la inconsistencia del SRS |
| G-12 | Cambio de estado de tarea: RF-TAR-04 admite cualquier cambio entre los seis estados; el esquema define un flujo restringido | Sin implementación documentada | AD-10: tabla de transiciones con el flujo del esquema como valor por defecto; Fixing solo con un fix abierto vinculado; confirmar (Propuesto) |
| G-13 | Gerente responsable: RF-PRO-04 exige rol Gerente; el esquema admite manager o admin | Sin implementación documentada | Se aplica el SRS (solo Gerente); confirmar |
| G-14 | Cancelación de sprint: RF-SPR-05 la permite a Administrador y Gerente; el esquema solo al Administrador cuando está activo | Sin implementación documentada | Se aplica el SRS; el motivo de cancelación requiere un campo nuevo (sección 3.5) |

### 2.2 Estilo Arquitectónico

**Patrón principal: monolito modular, SPA puramente de lado del cliente, organizada por features, con capas lógicas y flujo de datos unidireccional.** Un único artefacto estático contiene presentación, lógica de negocio y persistencia local. La modularidad es de código (carpetas y contextos por dominio), no de despliegue.

```
src/
├── components/   átomos y moléculas compartidos (Button, Modal, Badge, Input), sin lógica de dominio
├── context/      proveedores + reducers por dominio (estado global)
├── hooks/        useAppActions (orquestador), useNotifier, hooks de teclado y selectores
├── pages/        destinos de navegación (Dashboard, ProjectWorkspace, Users, Meetings...)
├── types/        tipos TypeScript y uniones discriminadas (NavState, TaskStatus...)
├── utils/        funciones puras: cálculo de horarios, velocidad, burndown, validaciones
└── data/         seed de demostración (seed.ts)
```

```
  PRESENTACIÓN   pages → secciones/pestañas → compuestos → compartidos        (React, Tailwind)
        │ lee con useContext / selectores            ▲ re-render
        │ dispatch(acción) / useAppActions           │
  APLICACIÓN     reducers + contextos + orquestador + can() + NavState
        │ usa                                        │ persiste (efecto)
  DOMINIO        tipos · reglas · tablas de transición · utilidades puras
        ▲ implementa puertos                         ▼
  INFRAESTRUCTURA   StorageAdapter(localStorage) · AIProvider(simulado) · reloj · ids
```

**Reglas de dependencia (verificables con ESLint):** la presentación no accede a localStorage ni al servicio de IA; los reducers y utils no importan React ni el DOM; el dominio no conoce la infraestructura; los contextos no se importan entre sí (la coordinación pasa por useAppActions).

**Responsabilidad por capa de componentes** (documento base): páginas (orquestan datos), secciones de feature (BacklogTab, KanbanTab, FixesTab), compuestos de dominio (SprintCard, KanbanColumn, FixCard), compartidos sin dominio y overlays montados en la raíz (CommandPalette, AIFloatingWidget, NotificationPanel).

**Mapa de contextos y persistencia**

| Contexto | Entidades que gobierna | Claves de localStorage | Acciones clave |
| --- | --- | --- | --- |
| AuthContext | users, sessions | dashnode\_users, dashnode\_current\_user | LOGIN, LOGOUT, UPDATE\_PROFILE |
| ProjectContext | projects, project\_members | dashnode\_projects | CREATE/UPDATE/DELETE\_PROJECT, SELECT\_PROJECT |
| TaskContext | epics, user\_stories, tasks, sprints | dashnode\_epics, dashnode\_user\_stories, dashnode\_tasks, dashnode\_sprints | CREATE\_TASK, UPDATE\_TASK\_STATUS, MOVE\_TASK, CREATE\_SPRINT |
| MeetingContext | meetings, meeting\_participants, availability | dashnode\_meetings, dashnode\_availability | CREATE\_MEETING, CANCEL\_MEETING, SET\_AVAILABILITY |
| FixContext | fixes, evidence, ai\_analyses | dashnode\_fixes | CREATE\_FIX, ADD\_EVIDENCE, REQUEST\_AI\_ANALYSIS, RESOLVE\_FIX |
| KnowledgeContext | knowledge\_entries | dashnode\_knowledge | CREATE\_ENTRY, APPROVE\_ENTRY, REJECT\_ENTRY |
| DevOpsContext | pipeline\_runs, pipeline\_steps, git\_branches | dashnode\_pipeline\_runs | TRIGGER\_PIPELINE, UPDATE\_STEP\_STATUS |
| NotificationContext | notifications | dashnode\_notifications | ADD\_NOTIFICATION, MARK\_READ, CLEAR\_ALL |
| AIContext | ai\_interactions | dashnode\_ai\_interactions | LOG\_INTERACTION, TOGGLE\_WIDGET |
| UIContext | navState, paleta, tema | Sin persistencia documentada (memoria) | NAVIGATE, TOGGLE\_COMMAND\_PALETTE |

**Decisión arquitectónica (supuesto):** el esquema declara 15 claves y no asigna clave a project\_members, meeting\_participants, evidence, ai\_analyses, pipeline\_steps, git\_branches ni sessions. Se asume que se persisten embebidas en su agregado raíz (por ejemplo, evidence dentro de cada fix). El audit\_logs (dashnode\_audit\_logs) lo escribe useAppActions, no un contexto propio. El árbol de componentes del documento base lista solo 5 contextos; se adopta el mapa completo de 10 contextos.

**Cómo se adapta el estilo al proyecto**

- **Sin servidor:** las reglas de integridad que una base de datos garantizaría (unicidad de correo, un único sprint activo, cascadas, claves foráneas) viven en reducers y se cubren con pruebas unitarias.
- **Rendimiento:** division de código por página (AD-15), selectores memoizados, escrituras coalescidas (AD-14) y paginación en cliente para listas largas (Propuesto, RNF-REN-02).
- **Fiabilidad:** Error Boundary por sección, hidratación validada y versionada (AD-12, AD-13).
- **Evolución:** cada contexto mantiene la misma interfaz de acciones; en la Fase 1 solo cambia el origen de los datos (adaptador), no los componentes ni los reducers.

**Alternativas descartadas**

| Alternativa | Motivo del descarte |
| --- | --- |
| Redux o Zustand | Añaden dependencia sin resolver un problema actual; los contextos por dominio bastan al volumen previsto |
| React Router desde el inicio | Contradice la línea base aprobada y exige configurar fallback en el hosting; se reserva para la Fase 3 |
| Backend as a Service (por ejemplo, Supabase) desde ahora | Cerraría las brechas G-01 a G-09, pero cambia el alcance del prototipo aprobado (RES-05) y su cuota gratuita está por verificar (R-01) |
| IndexedDB en lugar de localStorage | Mayor capacidad y API asíncrona, pero no está en la línea base; es la alternativa natural si el límite de 5–10 MB se alcanza (sección 3.3) |
| Microfrontends | Complejidad sin beneficio para un único equipo y un único artefacto |

## 3. VISTA FÍSICA

DashNode no tiene servidores de aplicación, base de datos ni colas: la topología se reduce a un nodo de distribución de archivos estáticos y al navegador del usuario, que ejecuta toda la lógica y custodia los datos.

### 3.1 Topología y modelo de distribución

```
  Usuario ─ Navegador ──HTTPS GET──▶ CDN / Hosting estático
               │                      index.html · assets/*.js · assets/*.css (hash de contenido) · sw.js (Propuesto)
               │
               ├─ Memoria JS (heap)    estado de React: 10 contextos (fuente de verdad en ejecución)
               ├─ localStorage         origen https://<host> · claves dashnode_* (JSON)
               ├─ Cache HTTP / Cache Storage   assets versionados
               └─ Salidas puntuales    Google Calendar (URL de plantilla) · enlaces externos (reunión, repo, actas)
```

| Nodo | Tipo | Artefactos | Responsabilidad |
| --- | --- | --- | --- |
| Navegador del usuario | Nodo de ejecución | Bundle JS y CSS, estado en memoria, localStorage | Renderizado, lógica de negocio, autorización, persistencia |
| CDN / hosting estático | Nodo de distribución | index.html, assets con hash, sw.js (Propuesto), cabeceras HTTP | Servir archivos inmutables por HTTPS; no ejecuta lógica |
| GitHub Actions | Nodo de construcción | Workflow de CI/CD | Validar, construir y publicar (sección 5) |
| Servicios externos | Destinos de navegación | Google Calendar; plataformas de reunión | Reciben datos solo por acción del usuario; no hay llamadas automáticas |

### 3.2 Carga inicial de assets

1. El navegador solicita `https://<host>/` y el CDN devuelve `index.html` con `Cache-Control: no-cache`, para revalidar siempre la versión vigente.
2. El HTML referencia el módulo de entrada (`/assets/index-[hash].js`) y la hoja de estilos que Tailwind v4 genera en el build (`/assets/index-[hash].css`). Ambos llevan hash de contenido y `Cache-Control: public, max-age=31536000, immutable`.
3. Se ejecuta `main.tsx`: `createRoot` monta `<App />`. Cada proveedor hidrata su estado desde localStorage antes de renderizar datos (proceso 4.11).
4. `AppShell` elige la vista según la sesión y `NavState`. Solo se descarga el fragmento de la página activa (AD-15); un visitante carga únicamente landing y login.
5. Los módulos pesados (Kanban, DevOps, métricas) se descargan bajo demanda y quedan en la caché HTTP.
6. (Propuesto, AD-16) Tras el evento `load` se registra el Service Worker, que precachea el shell y los fragmentos críticos.

| Táctica (Propuesto salvo indicación) | Objetivo SRS |
| --- | --- |
| Iconos como SVG en línea mediante importaciones nombradas de lucide-react (documento base) | RNF-REN-05 |
| Fuentes del sistema en vez de fuentes web, para no bloquear el primer render | RNF-REN-05, RNF-REN-06 |
| Importación dinámica del seed solo cuando localStorage está vacío | RNF-REN-06 |
| Presupuesto de tamaño del bundle verificado en CI (valor a fijar tras la primera medición) | RNF-REN-05 |
| Medición con auditoría automatizada y 4G emulada en el entorno desplegado | RNF-REN-05, RNF-REN-06 |

Sin Service Worker, abrir la aplicación sin red por primera vez o recargarla sin red falla, porque el HTML y los scripts se piden al CDN. El documento base afirma «sin red tras la carga inicial»; este SAD lo interpreta como operación offline dentro de la sesión ya cargada.

### 3.3 Interacción del navegador con el almacenamiento local

| Almacén | Uso en DashNode | Características | Riesgo |
| --- | --- | --- | --- |
| Memoria (estado de React) | Fuente de verdad durante la sesión | Rápida y volátil | Se pierde al cerrar o recargar la pestaña |
| localStorage | Persistencia de todas las entidades (claves dashnode\_\*) | Síncrono, solo cadenas, 5–10 MB según navegador, aislado por origen | Cuota; bloquea el hilo principal; legible por cualquier script del origen; puede ser purgado por el usuario o el navegador |
| Cache HTTP / Cache Storage | Assets estáticos y, con AD-16, el shell offline | Gestionado por el navegador | Versiones antiguas si no se invalidan |
| sessionStorage, cookies, IndexedDB | No se usan en la línea base | — | IndexedDB es la ruta si se supera la cuota |

**Lectura (hidratación).** Cada contexto inicializa `useReducer` con una función perezosa que lee su clave mediante el StorageAdapter, valida versión y forma, y recurre al seed si no hay datos o son inválidos.

**Escritura.** Cada cambio de estado dispara un efecto que serializa la colección afectada. Con AD-14 las escrituras se coalescen (debounce corto, valor inicial 250 ms, Propuesto) y se vacían de inmediato en `pagehide` y `visibilitychange`, para cumplir RNF-REN-08 (menos de 50 ms) sin perder el último cambio.

| Condición | Detección | Comportamiento |
| --- | --- | --- |
| Clave ausente | `getItem` devuelve null | Primera ejecución: se carga el seed |
| JSON inválido o forma inesperada | try/catch y guardas de tipo | Se descarta solo la colección afectada, se informa al usuario y se restaura su seed (G-09) |
| `QuotaExceededError` al escribir | try/catch en `setItem` | El estado en memoria se conserva; aviso de almacenamiento lleno; se bloquean nuevas evidencias y se ofrece exportar un respaldo |
| Almacenamiento no disponible (`SecurityError`, modo privado estricto) | try/catch en el adaptador | Modo solo memoria con aviso de que los datos no persistirán |
| Versión de esquema posterior a la soportada (por ejemplo, tras revertir un despliegue) | Comparación con `dashnode_schema_version` | Solo lectura y aviso; nunca se sobrescribe (sección 5.5) |
| Cambios hechos desde otra pestaña | Evento `storage` | Rehidratar o avisar (Propuesto); el documento base no soporta fusión multi-pestaña |

**Presupuesto de capacidad.** El volumen objetivo del documento base (menos de 100 proyectos y menos de 1000 tareas) cabe en la cuota. El riesgo dominante son las evidencias: la codificación base64 aumenta el tamaño un tercio, de modo que una imagen de 500 KB ocupa unos 667 KB y unas 7 imágenes agotarían 5 MB (estimación aritmética). Decisiones (Propuesto): tope configurable por evidencia (valor inicial 200 KB, RNF-REN-03); video solo por URL; alerta al 80 % de ocupación estimada, calculada con la longitud serializada de las claves dashnode\_\*.

**Seguridad del almacenamiento.** Cualquier script del origen lee localStorage, por lo que una falla XSS expone todos los datos. Mitigaciones: React escapa el contenido por defecto y se prohíbe `dangerouslySetInnerHTML` con contenido de usuario o de IA (RNF-SEG-10); CSP estricta (3.6); validación de esquemas de URL. Los datos no están cifrados. El cierre de sesión borra `dashnode_current_user`, pero no los datos de dominio, que son compartidos por todos los usuarios de demostración del mismo navegador.

### 3.4 Capacidad operativa offline

| Capacidad | Sin red tras la carga | Observación |
| --- | --- | --- |
| Navegación, CRUD, backlog, Kanban, sprints, métricas, notificaciones, paleta de comandos | Sí | Operan sobre memoria y localStorage |
| Cálculo de horarios y reuniones | Sí | Algoritmo local (proceso 4.9) |
| Asistente de IA y análisis de fix | Sí, simulados | Con IA real requerirá red; ante fallo o cuota se degrada con mensaje (RN-IAG-02) |
| Abrir Google Calendar | No | Ofrece copiar los datos de la reunión (RF-AGE-09) |
| Enlaces externos (reunión, repo, actas) | No | Solo navegan hacia fuera |
| Primera visita o recarga sin red | No, salvo AD-16 | Con Service Worker, el shell se sirve desde Cache Storage |
| Actualizar a una nueva versión | Requiere red | El Service Worker aplica la versión nueva al recargar y avisa al usuario (Propuesto) |

El estado de verdad es local, por lo que no existe cola de sincronización: los datos no viajan entre dispositivos y borrar los datos del sitio los destruye. Mitigaciones (Propuesto): exportación e importación de respaldo en JSON; solicitar almacenamiento persistente con `navigator.storage.persist()`; considerar que Safari puede purgar el almacenamiento escribible por scripts tras un periodo prolongado sin interacción (verificar en Safari 17). Al migrar a backend (Fase 1) se necesitará una estrategia de sincronización, fuera del alcance de la línea base.

### 3.5 Modelo de persistencia y brechas del esquema

```
Project ─┬─ ProjectMember
         ├─ Epic ── UserStory ── Task ──(fix_id)── Fix ─┬─ Evidence
         │              ▲          ▲                    └─ AIAnalysis
         ├─ Sprint ─────┘──────────┘   (sprint_id en historia y en tarea)
         ├─ Meeting ── MeetingParticipant
         ├─ KnowledgeEntry              (project_id nulo = conocimiento global)
         └─ PipelineRun ── PipelineStep ;  GitBranch
User ─── Notification · AIInteraction · AuditLog · Availability · Session
```

La integridad referencial no existe en el almacén; la garantizan los reducers (cascadas, claves foráneas lógicas, unicidad). El esquema se complementa con las siguientes brechas respecto al SRS:

| ID | Brecha del esquema | Requisito | Cambio propuesto |
| --- | --- | --- | --- |
| E-01 | knowledge\_entries no tiene indicador de visibilidad para desarrolladores | RN-DOC-01, RF-DOC-04 | Campo `visible_to_developers` (verdadero por defecto al aprobar) |
| E-02 | ai\_analyses usa un booleano `human_validated`; el SRS exige pendiente, validada o rechazada | RF-IAI-07 | `validation_status` como enumeración; se conservan validated\_by y validated\_at |
| E-03 | tasks no guarda el estado previo para restaurarlo al resolver el fix | RN-ISS-01 | Campo `status_before_fix` |
| E-04 | sprints no guarda el motivo de cancelación | RF-SPR-05 | Campo `cancel_reason` |
| E-05 | El historial de cambios de estado de tarea no tiene tabla propia | RF-TAR-04 | Usar audit\_logs con la acción `task.status_changed` (usuario, fecha, valor previo y nuevo) en cada transición |
| E-06 | notifications.type no incluye «issue asignado» | RF-NOT-01 | Añadir el tipo `fix_assigned` |
| E-07 | availability se guarda por semana (`week_start`); el SRS exige continuidad entre semanas | RF-DIS-03 | Selector que hereda el último registro anterior cuando la semana no tiene datos |
| E-08 | users no marca la credencial temporal ni el cambio obligatorio | RN-USU-01 | Campo `must_change_password` (Propuesto) |
| E-09 | La cascada de eliminación de proyecto no menciona project\_members ni git\_branches | RF-PRO-06, D-23 | Incluirlos; el borrado definitivo o lógico sigue pendiente en D-23 |
| E-10 | meetings.status no define quién pasa a in-progress o completed | RF-AGE-06, RF-AGE-12 | Derivar «pasada» por reloj al leer; persistir completed al registrar el acta |
| E-11 | Tareas sin responsable | RF-USU-07 | Sin cambio: `assignee_id` nulo significa «sin responsable» |

### 3.6 Seguridad del cliente y salidas de red

| Salida | Mecanismo | Controles |
| --- | --- | --- |
| Google Calendar | URL de plantilla (título, fecha, duración, enlace, invitados) abierta con `window.open` por clic del usuario | Sin credenciales de Google (RNF-COM-02); la inclusión de invitados no está garantizada (R-04); ante fallo, copiar datos |
| Enlaces de reunión, repositorio y actas | Navegación a una pestaña nueva con `rel=noopener noreferrer` | Aceptar solo esquemas http y https (bloquea `javascript:`); RNF-INT-07 |
| Servicios de IA, correo, CI/CD | Ninguna en la línea base | Sin `fetch` hacia terceros; `connect-src 'self'` lo hace verificable |

Política de seguridad de contenido recomendada (Propuesto), servida como cabecera HTTP por el hosting:

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
  img-src 'self' data: blob:; connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'
```

`img-src data:` permite mostrar evidencias en base64 y `style-src 'unsafe-inline'` cubre estilos en línea de React; se endurece si el código no los usa. `frame-ancestors` solo es efectivo como cabecera, lo que favorece un hosting que permita configurarlas (sección 5.4).

## 4. VISTA FUNCIONAL O LÓGICA

Se documentan los 12 procesos core. Todos comparten el mismo mecanismo: la interfaz emite una acción, la política can() la autoriza, el reducer valida y produce el nuevo estado, y un efecto lo persiste (AD-04, AD-08). Las operaciones que tocan varios dominios pasan por useAppActions (AD-07).

| Proceso | Contextos principales | Requisitos del SRS |
| --- | --- | --- |
| 4.1 Autenticación, sesión y autorización | Auth, UI | RF-AUT, RN-AUT, RN-USU-03 |
| 4.2 Navegación y paleta de comandos | UI | RF-PRO-07, RF-CMD, RF-NOT-04 |
| 4.3 Gestión de usuarios y proyectos | Auth, Project, Task | RF-USU, RF-PRO, RN-USU, RN-PRO |
| 4.4 Backlog y tareas | Task, Project | RF-TAR, RN-TAR |
| 4.5 Sprints y tablero Kanban | Task, Notification | RF-SPR, RF-KAN, RN-SPR-01 |
| 4.6 Issues, evidencias y análisis de IA | Fix, Task, AI, Notification | RF-ISS, RF-IAI, RN-ISS-01, RN-IAI, RN-IAG |
| 4.7 Asistente de IA y métricas | AI | RF-IAV, RF-IAM, RN-IAV |
| 4.8 Base de conocimiento con aprobación | Knowledge, Notification | RF-DOC, RN-DOC |
| 4.9 Disponibilidad y agendamiento de reuniones | Meeting, Notification | RF-DIS, RF-AGE, RN-AGE |
| 4.10 Notificaciones y orquestación entre contextos | Notification, todos | RF-NOT, RN-NOT-01 |
| 4.11 Persistencia, arranque y recuperación | Todos | RNF-FIA-03, RNF-REN-08 |
| 4.12 Dashboard y DevOps | DevOps, lectura de todos | RF-PRO-08, RF-DVO |

### 4.1 Autenticación, sesión y autorización

- **Objetivo:** identificar a la persona, mantener su sesión y restringir cada vista y operación según rol, membresía, asignación y autoría.
- **Procesos involucrados:** LandingPage y LoginPage; verificación de credenciales contra dashnode\_users (rechaza cuentas con is\_active falso); creación, restauración y cierre de sesión; cambio de contraseña propia; AuthGuard en AppShell; política can(); renderizado por rol de menú, pestañas y comandos.
- **Interacciones y comunicación:** LoginPage emite LOGIN a AuthContext. AppShell lee `isAuthenticated` y emite NAVIGATE a UIContext. can(usuario, acción, recurso) es una función pura que reciben los hooks de cada módulo; los reducers la reutilizan para no depender de la interfaz (AD-08).
- **Ciclo de vida:**
  1. El visitante abre la landing y navega a login.
  2. El formulario valida campos y despacha LOGIN.
  3. El reducer busca el correo, compara la credencial y comprueba is\_active; ante cualquier fallo devuelve el mismo mensaje.
  4. Con éxito fija `currentUser` y `isAuthenticated`; un efecto persiste `dashnode_current_user` y se navega al dashboard.
  5. Al recargar, AuthContext hidrata la sesión; si `expires_at` (8 h) venció se vuelve a la landing. El esquema indica que la expiración no se aplica; validarla al hidratar es una decisión (Propuesto).
  6. LOGOUT elimina la clave de sesión y navega a la landing.
- **Operaciones funcionales y resultado:** entradas: correo y contraseña (en el cambio de contraseña, la actual y la nueva con mínimo de 8 caracteres, Propuesto). Validaciones: formato, mensaje único ante credenciales inválidas (RF-AUT-02), rechazo de cuentas desactivadas, contraseña actual correcta (RF-USU-03). Salida: sesión y vista acorde al rol; un acceso sin sesión a una página protegida redirige a la landing sin mostrar datos (RF-AUT-08). Brechas: G-01, G-02, G-03, G-06, G-07, G-11.

**Criterios de autorización que evalúa can()**

| Criterio | Regla del SRS | Ejemplo |
| --- | --- | --- |
| Rol | Matriz 7.2 | Solo el Administrador elimina proyectos |
| Membresía | RN-PRO-01 | Un desarrollador no abre un proyecto del que no es miembro |
| Asignación | RN-TAR-01 | Un desarrollador solo mueve sus tareas |
| Autoría | RN-DOC-04 | Nadie aprueba su propia entrada, ni siquiera el Administrador |
| Creador | RN-AGE-05 | Solo quien creó la reunión la cancela |
| Solicitante | RN-IAI-02 | Eliminan una respuesta de IA el Administrador, el Gerente y quien la pidió |

### 4.2 Navegación y paleta de comandos

- **Objetivo:** cambiar de página y pestaña sin URLs y dar acceso por teclado a páginas y acciones.
- **Procesos involucrados:** estado `NavState`; renderizado condicional en AppShell; ProjectWorkspacePage con ProjectTabBar (pestañas filtradas por rol, RF-PRO-07); CommandPalette (Ctrl+K o Cmd+K); NotificationPanel con enlaces a entidades.
- **Interacciones y comunicación:** UIContext es el único dueño de `navState`. Cualquier componente despacha NAVIGATE con un NavState tipado. Un listener global en App.tsx abre la paleta, que construye su lista desde un registro de comandos filtrado por can(). Las notificaciones guardan en `action_url` el NavState de destino.
- **Ciclo de vida:**
  1. Un clic, Enter en un comando o una notificación despacha NAVIGATE.
  2. El reducer reemplaza `navState`; AppShell renderiza la página y Suspense muestra el estado de carga mientras llega el fragmento (AD-15).
  3. El foco se mueve al encabezado de la nueva vista (Propuesto, WCAG 2.2).
  4. Paleta: Ctrl+K alterna la visibilidad, el foco queda en el campo; cada pulsación filtra en memoria (menos de 50 ms, RNF-REN-09); flechas y Enter ejecutan; Escape cierra y devuelve el foco al elemento previo (RF-CMD-04).
- **Operaciones funcionales y resultado:** entrada: NavState o texto de búsqueda. Validación: la página destino debe estar permitida para el rol, si no se redirige al dashboard; un proyecto no accesible devuelve acceso denegado. Salida: vista renderizada o comando ejecutado. Limitación conocida: sin URL ni historial, recargar regresa a la landing o al dashboard (RA-04, Fase 3).

### 4.3 Gestión de usuarios y proyectos

- **Objetivo:** administrar cuentas, roles y membresía de proyectos sin perder el trabajo existente.
- **Procesos involucrados:** UsersPage (Administrador): listar, buscar, filtrar por rol, crear, editar y desactivar; ProfilePage; ProjectsPage: crear y editar proyecto, gerente responsable, estado, miembros y eliminación; resumen con progreso, velocidad e issues abiertos (RF-PRO-08).
- **Interacciones y comunicación:** AuthContext (users) y ProjectContext. La desactivación y la eliminación de proyecto son operaciones transversales orquestadas por useAppActions: la primera toca Auth, Task y el registro de auditoría; la segunda, Project, Task, Meeting, Fix, Knowledge y DevOps.
- **Ciclo de vida:**
  1. Crear usuario: el formulario valida el rol permitido según quien crea (Administrador: Gerente o Desarrollador; Gerente: solo Desarrollador; nunca Administrador, RN-USU-10 y RF-USU-01) y la unicidad del correo; se despacha CREATE\_USER.
  2. Desactivar: confirmación y `deactivateUser`, que en un solo lote marca `is_active` falso, pone `assignee_id` en nulo en las tareas no completadas, conserva las completadas y registra `user.deactivated` en audit\_logs (RNF-SEG-07). Al hidratar se detecta un lote parcial (G-08).
  3. Crear proyecto: estado inicial planning (S-10); validar nombre (máximo 100 caracteres), fin posterior al inicio, URL válida y gerente responsable (G-13).
  4. Eliminar proyecto: confirmación del Administrador, cascada según el esquema más E-09 y registro de auditoría. Borrado definitivo o lógico sigue en D-23.
- **Operaciones funcionales y resultado:** validaciones de correo único, rol permitido, estados y prioridades en listas cerradas, miembros existentes. Salida: lista actualizada, tareas «Sin responsable» disponibles para reasignar (RF-USU-07) y proyectos visibles según RN-PRO-01. Propuesto mientras D-22 siga abierta: impedir desactivar al último Administrador activo o a un gerente responsable sin reasignar el proyecto.

### 4.4 Backlog y tareas

- **Objetivo:** descomponer el trabajo en épica, historia y tarea, asignarlo y seguir su avance.
- **Procesos involucrados:** BacklogTab (EpicList, UserStoryList, TaskList) con edición en línea y orden por arrastre (campo `order`); puntos Fibonacci, prioridad, etiquetas y asignación; búsqueda y filtros (RF-TAR-12); MyTasksPage con filtros por estado y proyecto; acción «Reportar fix».
- **Interacciones y comunicación:** TaskContext gobierna epics, user\_stories, tasks y sprints. ProjectContext aporta los miembros asignables. Los selectores aplican RN-TAR-01 antes de filtrar. La notificación `task_assigned` se emite desde useAppActions.
- **Ciclo de vida:**
  1. Acción del usuario; can(usuario, `task.create`, proyecto) la autoriza.
  2. Se despacha CREATE\_TASK; el reducer exige historia existente (RN-TAR-03), puntos en 1, 2, 3, 5, 8, 13 o 21 (RN-TAR-02) y un responsable que sea miembro con rol distinto de Administrador (RF-TAR-02).
  3. El nuevo estado se persiste y se notifica al responsable.
  4. Cambio de estado: UPDATE\_TASK\_STATUS consulta la tabla TASK\_TRANSITIONS y can(); registra `task.status_changed` en audit\_logs (E-05). Cuando todas las tareas de una historia están completadas, la historia se considera completada (derivado).
- **Operaciones funcionales y resultado:** flujo por defecto de TASK\_TRANSITIONS, tomado del esquema: `todo → in-progress → code-review → testing → completed`; `testing → fixing → in-progress`. El estado `fixing` solo se alcanza con un fix abierto vinculado (regla de integridad 3). Si el SRS requiere cualquier transición, basta ampliar la tabla (G-12). Salida: jerarquía anidada, vista «Mis tareas» con solo elementos propios y estados vacíos con acción sugerida.

### 4.5 Sprints y tablero Kanban

- **Objetivo:** planificar iteraciones, ejecutarlas y visualizar el flujo, la velocidad y el burndown.
- **Procesos involucrados:** SprintsTab (SprintCard, SprintPlanning): crear, mover historias por arrastre o selección, iniciar, completar y cancelar; KanbanTab con seis KanbanColumn y KanbanCard; gráficos de velocidad y burndown; filtros por responsable, prioridad y etiqueta; detalle de tarea.
- **Interacciones y comunicación:** TaskContext (sprints, historias, tareas) y NotificationContext (`sprint_started`). Velocidad, burndown y puntos del sprint son selectores puros (AD-11). El Kanban y «Mis tareas» despachan la misma acción UPDATE\_TASK\_STATUS, lo que garantiza comportamiento idéntico (RF-TAR-14).
- **Ciclo de vida:**
  1. Sprint: `planning → active → completed`, o `planning → cancelled`, o `active → cancelled` con motivo (G-14); un sprint completado es de solo lectura.
  2. Iniciar: el reducer rechaza si ya hay otro activo (RN-SPR-01) y notifica a los miembros.
  3. Kanban: se arrastra una tarjeta; `onDrop` entrega el id y la columna destino; se despacha UPDATE\_TASK\_STATUS; can() y TASK\_TRANSITIONS lo validan; el reflejo en pantalla toma menos de 100 ms (RNF-REN-07) y se persiste.
  4. Completar: la velocidad es la suma de puntos de las historias completadas; las no terminadas siguen vinculadas al sprint según el esquema (destino definitivo en D-24).
- **Operaciones funcionales y resultado:** validaciones de fechas (fin posterior al inicio), puntos y permisos (un desarrollador no mueve tarjetas ajenas). Burndown: restantes(d) = total − suma de puntos de historias cuyo evento de finalización en audit\_logs es anterior o igual al día d, contra una línea ideal lineal. Accesibilidad: como alternativa al arrastre, el detalle de la tarjeta ofrece un selector de estado operable con teclado (RNF-INT-01); las tareas en Corrección se distinguen con icono y texto (RF-KAN-06). Sin sprint activo se muestra el estado vacío.

### 4.6 Issues (Fix), evidencias y análisis de IA

- **Objetivo:** registrar defectos con evidencia, obtener recomendaciones de IA y resolverlos con validación humana, manteniendo coherente la tarea afectada.
- **Procesos involucrados:** FixesTab (FixCard, EvidenceUpload, AIAnalysisPanel): crear, adjuntar evidencia, listar y filtrar, asignar (Administrador o Gerente), solicitar análisis, validar o rechazar (Administrador o Gerente), resolver con nota y vincular a una tarea.
- **Interacciones y comunicación:** FixContext (fixes, evidencia, análisis), TaskContext (estado Corrección y `fix_id`), AIContext (registro), NotificationContext y el puerto AIProvider. Las operaciones `reportFix`, `requestAnalysis` y `resolveFix` de useAppActions las coordinan.
- **Ciclo de vida:**
  1. Reportar desde una tarea: CREATE\_FIX y, en la misma operación, la tarea pasa a `fixing` con `fix_id` y `status_before_fix` (E-03); se notifica al gerente responsable.
  2. Evidencia: se valida tipo y tamaño (G-04) y se despacha ADD\_EVIDENCE.
  3. Análisis por acción explícita: REQUEST\_AI\_ANALYSIS invoca AIProvider con la descripción y la evidencia, con tiempo de espera de 30 s (RNF-REN-04). La respuesta (máximo 150 palabras, sugerencias, confianza) se guarda como no verificada, con estado pendiente y aviso de validación, y se registra en AIContext.
  4. Validación humana: solo Administrador o Gerente cambian el estado; mientras no esté validada ninguna acción automática se ejecuta (RN-IAG-03).
  5. Resolver: la nota es obligatoria; RESOLVE\_FIX deja el fix en `resolved` con `resolved_at`, desvincula la tarea y restaura `status_before_fix` o el estado elegido (RN-ISS-01), y notifica.
- **Operaciones funcionales y resultado:** flujo de fix `open → in-progress → resolved → closed`; `open → closed` solo Administrador. Validaciones: título, severidad y tipo obligatorios; asignado miembro del proyecto; evidencia de tipo y tamaño admitidos. Errores de IA (carga, formato, fallo, tiempo agotado, cuota) muestran su mensaje, conservan issue y evidencia y permiten reintentar (RF-IAI-06). Eliminar una respuesta exige confirmación y queda auditado (RNF-SEG-07). Salida: issue con evidencia, panel de análisis con su estado, tarea sincronizada.

### 4.7 Asistente de IA y métricas de IA

- **Objetivo:** ofrecer asistencia conversacional con el contexto del proyecto, registrar toda interacción y medir su uso y calidad.
- **Procesos involucrados:** AIFloatingWidget (botón en la esquina inferior derecha y ventana de chat); entrada de texto y, según el SRS, captura de voz con MediaRecorder solo tras acción explícita, con límite de 60 s (Propuesto); estados inactivo, grabando, procesando, respondida y error, con texto e indicador y nunca solo color (RF-IAV-05); valoración de 1 a 5; AIMetricsTab para Administrador y Gerente (total, latencia promedio, tokens, interacciones por usuario); control de cuota por usuario y día (RNF-REN-03). El documento base solo simula el chat de texto; la voz se especifica como adaptador.
- **Interacciones y comunicación:** AIContext (interacciones, `isWidgetOpen`). El puerto AIProvider expone `transcribe(audio)`, `complete(mensajes, contexto)` y `analyzeEvidence(...)`; el adaptador simulado responde con temporizador. ProjectContext aporta solo el contexto mínimo del proyecto abierto: nombre, estado, sprint activo y conteos (RF-IAV-07).
- **Ciclo de vida:**
  1. TOGGLE\_WIDGET abre la ventana.
  2. La persona escribe o pulsa grabar; se solicita el permiso del micrófono y, si se deniega o no existe, se informa y no se captura nada (RN-IAV-01).
  3. Al detener o al llegar al límite, el audio queda como Blob en memoria, se envía a `transcribe` y se descarta al terminar (RN-IAV-02).
  4. El texto y el contexto van a `complete` con tiempo de espera de 30 s; el indicador de procesamiento aparece en menos de 1 s (RNF-REN-04).
  5. La respuesta se muestra en el chat y LOG\_INTERACTION guarda usuario, proyecto, solicitud, respuesta, tipo, modelo, tokens y latencia, sin audio (RF-IAM-04).
  6. La valoración actualiza el registro; los selectores recalculan las métricas.
- **Operaciones funcionales y resultado:** validaciones: audio no vacío y de menos de 60 s, soporte de captura en el navegador (mensaje en caso contrario, RNF-COM-01), cuota diaria (al agotarse se degrada con mensaje, RN-IAG-02), valoración entre 1 y 5. Salida: conversación cronológica y registro consultable en `dashnode_ai_interactions`; las métricas coinciden con los registros (RF-IAM-01, RF-IAM-02). Si el historial del chat persiste y es visible para la persona sigue pendiente en D-13. Con IA real, texto e imagen requieren un proxy con secretos en servidor (G-05); la voz a texto puede ejecutarse en el navegador sin secretos (opciones de D-14).

### 4.8 Base de conocimiento con aprobación

- **Objetivo:** capturar documentación por proyecto con control de calidad y de visibilidad antes de compartirla con desarrolladores.
- **Procesos involucrados:** KnowledgeTab con KnowledgeList (búsqueda por título, contenido y etiquetas; filtro por categoría técnica, funcional, reunión, general o prompt; ancladas al inicio); creación y edición con texto Markdown y/o enlace externo; ApprovalQueue (Administrador y Gerente): aprobar, rechazar con motivo, restringir visibilidad y anclar; reenvío del autor tras un rechazo; versiones (`version`, `parent_id`).
- **Interacciones y comunicación:** KnowledgeContext y NotificationContext (`knowledge_approved` y `knowledge_rejected` hacia el autor). can() evalúa rol y autoría. La búsqueda es un selector que opera sobre la colección ya autorizada, de modo que nunca filtra contenido restringido.
- **Ciclo de vida:**
  1. Cualquier usuario crea una entrada: queda `pending` y no es visible para otros desarrolladores (RN-DOC-05).
  2. APPROVE\_ENTRY exige rol de Administrador o Gerente y `approved_by` distinto de `author_id` (RN-DOC-04); la entrada pasa a `approved`, con visibilidad habilitada por defecto (E-01), y se notifica.
  3. REJECT\_ENTRY exige un motivo; la entrada pasa a `rejected` y se notifica.
  4. El autor revisa y reenvía: vuelve a `pending` y conserva la retroalimentación previa (RF-DOC-11).
  5. Cambios de visibilidad, anclado, aprobaciones y rechazos se registran en audit\_logs (RNF-SEG-07).
- **Operaciones funcionales y resultado:** validaciones: título y categoría obligatorios; texto o enlace; enlace con esquema http o https. Salida: Administrador y Gerente ven todo; un desarrollador ve las aprobadas y visibles más las propias. Una consulta directa por id a una entrada no permitida se niega sin devolver contenido ni enlace (RF-DOC-05); la comprobación está en la capa de selección, no en la interfaz. Riesgos: R-08 (el recurso externo conserva sus propios permisos) y D-28 (autor como único aprobador disponible).

### 4.9 Disponibilidad y agendamiento de reuniones

- **Objetivo:** capturar la disponibilidad semanal, calcular horarios comunes y programar reuniones con confirmación y notificación.
- **Procesos involucrados:** AvailabilityPage: rejilla semanal de 7 días por 24 horas en bloques de una hora (todos los roles) y rejilla del equipo (Administrador y Gerente); formulario de cálculo (intervalo, días, participantes, duración); lista de horarios; modal de confirmación (título, tipo daily, planning, review, retro o general, enlace opcional prellenado con el predeterminado del proyecto); MeetingsPage y CalendarPage; aceptación o rechazo; cancelación; acta; apertura de Google Calendar.
- **Interacciones y comunicación:** MeetingContext (meetings, participants, availability), ProjectContext (miembros y enlace predeterminado), NotificationContext y la utilidad pura `computeCommonSlots`.
- **Ciclo de vida:**
  1. Cada persona guarda su semana con SET\_AVAILABILITY; una semana sin registro hereda el último anterior (E-07, RF-DIS-03).
  2. Administrador o Gerente define los parámetros; se exige intervalo válido, al menos un día, un participante y una duración que quepa (RF-AGE-01).
  3. `computeCommonSlots` genera, por día y participante, un arreglo booleano de 24 horas; hace el AND entre participantes y acepta cada hora de inicio si los ⌈duración / 60⌉ bloques contiguos están en la intersección y dentro del intervalo (D-08 sigue abierta para duraciones no múltiplos de una hora). El costo es proporcional a días × horas × participantes, unas 3 400 operaciones en el peor caso del SRS (7 × 24 × 20), muy por debajo del límite de 3 s (RNF-REN-01).
  4. Sin resultados se muestra el mensaje y no se permite programar (RF-AGE-02).
  5. Al elegir un horario se abre el modal; CREATE\_MEETING registra la reunión y sus participantes con RSVP pendiente, notifica `meeting_scheduled` y navega a Reuniones.
  6. Cada invitado acepta o rechaza; puede cambiarlo antes de la reunión.
  7. CANCEL\_MEETING solo procede si el actor es `creator_id` (RN-AGE-05); can() lo niega incluso al Administrador.
  8. Realizada la reunión, Administrador o Gerente guardan resumen y URL del acta (RF-AGE-12).
  9. El botón de Google Calendar abre la URL de plantilla por clic; si falla, se ofrece copiar los datos (RF-AGE-09).
- **Operaciones funcionales y resultado:** validaciones: título y tipo obligatorios, URL válida, participantes miembros del proyecto. Decisión (Propuesto): `scheduled_at` se guarda en UTC (ISO 8601) y se muestra en la zona del navegador; las franjas de disponibilidad se interpretan en la hora local de quien las registró, lo que solo es exacto para equipos en una misma zona (D-09 abierta). Conflictos de disponibilidad, reuniones concurrentes y cambio de horario (D-10, D-11) no se implementan hasta que se decidan. Salida: reunión visible en lista y calendario con su tipo, y participantes notificados.

### 4.10 Notificaciones y orquestación entre contextos

- **Objetivo:** informar a las personas afectadas por eventos relevantes y coordinar operaciones que cruzan dominios sin acoplar los contextos.
- **Procesos involucrados:** useAppActions (mediador); useNotifier; NotificationBell con contador de no leídas; NotificationPanel con marcado individual y masivo, borrado total con confirmación y navegación a la entidad (RF-NOT-02 a RF-NOT-05).
- **Interacciones y comunicación:** useAppActions recibe los dispatchers de todos los contextos y expone operaciones de negocio (`createFix`, `startSprint`, `deactivateUser`, `scheduleMeeting`, `approveEntry`). Cada operación es un único handler que emite un lote de dispatches, que React agrupa en un solo renderizado. Ningún reducer invoca a otro.
- **Ciclo de vida:** acción de usuario → useAppActions autoriza con can() → despacha a los contextos de dominio → despacha ADD\_NOTIFICATION por cada destinatario → escribe audit\_logs si el evento es auditable → un render → los efectos persisten. useNotifier observa cambios derivables, como una ejecución de pipeline fallida, y evita duplicados con la clave (tipo, entidad, usuario) (Propuesto).
- **Operaciones funcionales y resultado:**

| Evento (notifications.type) | Destinatarios |
| --- | --- |
| task\_assigned | Responsable de la tarea |
| sprint\_started, sprint\_completed | Miembros del proyecto |
| fix\_reported | Gerente responsable |
| fix\_assigned (nuevo, E-06) | Desarrollador asignado |
| fix\_resolved | Persona que reportó el fix |
| meeting\_scheduled, meeting\_cancelled | Participantes de la reunión |
| knowledge\_approved, knowledge\_rejected | Autor de la entrada |
| pipeline\_success, pipeline\_failed | Quien lanzó la ejecución y el gerente responsable (Propuesto) |
| mention | Persona mencionada |

RN-NOT-01 se cumple con selectores que filtran por `user_id`; el contador es el número de no leídas del usuario actual. Como el almacén es compartido por todos los usuarios de demostración del navegador, el aislamiento depende de los selectores (G-01).

### 4.11 Persistencia, arranque y recuperación

- **Objetivo:** reconstruir el estado al abrir la aplicación y mantener localStorage consistente con la memoria.
- **Procesos involucrados:** arranque (`main.tsx` → App → proveedores); hidratación por contexto; validación y migración por versión; seed; escritura coalescida; manejo de cuota; exportación e importación de respaldo y reinicio de datos de demostración (Propuesto).
- **Interacciones y comunicación:** los proveedores usan el puerto StorageAdapter (`read`, `write`, `remove`, `estimateUsage`) y nunca llaman a localStorage directamente. El adaptador informa a UIContext el estado del almacenamiento (correcto, casi lleno, lleno o no disponible) para mostrar avisos; escucha `pagehide` y `storage`.
- **Ciclo de vida:**
  1. El navegador carga el bundle y se monta la aplicación.
  2. Cada proveedor calcula su estado inicial con una función perezosa: lee la clave, la parsea, valida versión y forma con guardas de tipo (sin `any`) y migra si la versión es anterior; ante cualquier fallo usa el seed de esa colección (AD-13).
  3. Se repara la integridad mínima: una tarea en `fixing` sin fix válido vuelve a su estado previo o a `in-progress`; una ejecución de pipeline en `running` pasa a `cancelled`; una desactivación a medias se completa (G-08).
  4. Se renderiza con datos.
  5. En cada cambio, un efecto marca la clave como pendiente y un temporizador la escribe tras 250 ms; `pagehide` y `visibilitychange` vacían la cola inmediatamente (AD-14).
  6. Un error de cuota o de disponibilidad se gestiona como en la sección 3.3; el cierre de sesión no borra datos de dominio.
- **Operaciones funcionales y resultado:** entradas: claves dashnode\_\* y `dashnode_schema_version`. Validaciones: JSON válido, forma esperada e integridad referencial mínima. Salida: estado consistente o aviso explícito; el sistema no falla por datos locales corruptos (RNF-FIA-03). El respaldo en JSON permite recuperar datos que no existen en ningún servidor (G-09).

### 4.12 Dashboard y DevOps

- **Objetivo:** mostrar KPIs según el rol y la visualización de CI/CD, en modo de solo lectura salvo la ejecución manual del pipeline.
- **Procesos involucrados:** DashboardPage (StatCard, RecentActivityFeed, ProjectSummaryList, SprintBurndown): el Administrador ve todo, el Gerente sus proyectos y el Desarrollador sus tareas; DevOpsTab con PipelineVisualizer (lint, test, build, deploy), historial, puertas de calidad (cobertura y puntaje de lint), registros por paso y GitFlowDiagram; ejecución manual para Administrador y Gerente (RF-DVO-05).
- **Interacciones y comunicación:** el dashboard no tiene estado propio: agrega con selectores memoizados sobre Project, Task, Fix y Notification. DevOpsContext gobierna pipeline\_runs, pipeline\_steps y git\_branches, sembrados con ejecuciones simuladas mientras D-25 siga abierta.
- **Ciclo de vida:**
  1. Dashboard: al renderizar, los selectores filtran por rol y calculan progreso (puntos completados sobre puntos totales, Propuesto en el SRS), velocidad e issues abiertos.
  2. DevOps: TRIGGER\_PIPELINE crea una ejecución `pending` con `trigger_type` manual; una secuencia temporizada simula los pasos con UPDATE\_STEP\_STATUS (running, luego success o failed, con duración, registros, cobertura y resultado de la puerta de calidad).
  3. Al terminar, se fija el estado de la ejecución y se notifica `pipeline_success` o `pipeline_failed`; los temporizadores se cancelan al desmontar.
- **Operaciones funcionales y resultado:** validación: solo Administrador o Gerente lanzan ejecuciones (can()). Salida: vistas de lectura con datos simulados. Con un proveedor real de CI/CD, por ejemplo GitHub Actions, se necesitan secretos en servidor (RNF-SEG-05, R-10).

## 5. VISTA DE DESPLIEGUE

### 5.1 Empaquetado

- **Cadena de build:** `npm ci` → `eslint` → `tsc --noEmit` → `vitest run --coverage` → `vite build`.
- **Artefacto:** la carpeta `dist/`, totalmente estática: `index.html`, `assets/` con JS y CSS con hash de contenido, iconos y, con AD-16, `sw.js` y `manifest`. No hay servidor Node en producción.
- **Configuración de Vite:** la opción `base` es `/` con dominio propio o con Cloudflare Pages, y `/<repositorio>/` en GitHub Pages. Las variables `VITE_*` quedan incrustadas en el bundle y son públicas: nunca contienen secretos (RNF-SEG-05). Los sourcemaps no se publican en producción (Propuesto).
- **Versionado:** SemVer en `package.json`; cada build inyecta versión y commit, visibles en la página del manual de usuario. `dashnode_schema_version` evoluciona de forma independiente de la versión de la aplicación.
- **Navegación por estado:** al no haber rutas por URL, el hosting no necesita reglas de reescritura hacia `index.html` (AD-05), por lo que funciona en cualquier hosting estático.

### 5.2 Entornos

| Entorno | Propósito | Dónde corre | Datos | Controles |
| --- | --- | --- | --- | --- |
| Desarrollo | Codificar con recarga en caliente | `vite` en localhost (puerto 5173 por defecto) | localStorage del origen local, inicializado con el seed | ESLint y tsc en el editor |
| Pruebas / CI | Verificación automatizada | Ejecutor de GitHub Actions con Vitest (jsdom) | Almacenamiento simulado en memoria | Lint, tipos, pruebas, cobertura |
| Previsualización (Propuesto) | Revisión funcional y visual por pull request | URL efímera del hosting | Seed nuevo, porque el origen es distinto | Auditoría de accesibilidad y rendimiento |
| Producción | Uso real o de demostración | Hosting estático con CDN y HTTPS en el dominio final | localStorage del origen de producción | CSP, HSTS, caché inmutable |

Cada entorno tiene un origen distinto y, por tanto, datos aislados. Cambiar el dominio o el puerto de producción deja a las personas usuarias con un almacén vacío (RA-12): el dominio final debe fijarse antes de la primera publicación.

### 5.3 Flujo de Integración y Despliegue Continuo

```
  feature/* ──PR──▶ develop ──release/*──▶ main ──tag vX.Y.Z──▶ Producción
     │                │                     │
     ▼                ▼                     ▼
  CI en PR:        CI + previsualización   CI + publicación del artefacto dist/ (inmutable)
  lint·tipos·      (URL efímera)           + verificación posterior al despliegue
  pruebas·build
```

La estrategia de ramas sigue Git Flow, el mismo modelo que muestra el módulo DevOps (main, develop, feature, release, hotfix).

| Etapa | Herramienta | Criterio de aprobación | Requisito |
| --- | --- | --- | --- |
| Instalación reproducible | `npm ci` con lockfile | Sin cambios en el lockfile | RNF-MAN |
| Lint | ESLint con regla contra `any` | 0 errores y 0 usos de `any` | RNF-MAN-03 |
| Tipos | `tsc --noEmit` en modo estricto | 0 errores | RNF-MAN-02 |
| Pruebas | Vitest y Testing Library | Todas verdes; cobertura de líneas de al menos 70 % en autorización y reglas | RNF-MAN-01 |
| Tamaño de componentes | Regla o script automático | Ningún componente supera 300 líneas | RNF-MAN-04 |
| Build | `vite build` | Éxito y presupuesto de tamaño respetado | RNF-REN-05 |
| Escaneo de secretos | Herramienta gratuita (por ejemplo, gitleaks) sobre el repositorio y `dist/` | 0 secretos | RNF-SEG-05 |
| Auditoría de dependencias (Propuesto) | `npm audit` | Sin vulnerabilidades altas o críticas sin justificar | — |
| Accesibilidad y rendimiento | Auditoría automatizada sobre la previsualización | 0 errores críticos; TTI menor de 2 s | RNF-INT-01, RNF-REN-06 |
| Publicación | Acción del hosting | `dist/` publicado solo desde main | AD-17 |
| Verificación posterior | Prueba de humo (landing y login) y revisión de cabeceras | HTTP 200 y CSP presente | RNF-SEG-04 |

Ejemplo orientativo del workflow (verificar las versiones vigentes de las acciones antes de adoptarlo; los secretos del token viven solo en el CI):

```yaml
name: ci-cd
on:
  pull_request:
  push:
    branches: [main, develop]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 'lts/*', cache: npm }
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm run test -- --coverage
      - run: npm run build
      - uses: actions/upload-artifact@v4
        with: { name: dist, path: dist }
  deploy:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with: { name: dist, path: dist }
      - uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: pages deploy dist --project-name=dashnode
```

### 5.4 Hosting y cabeceras HTTP

Se recomienda Cloudflare Pages porque permite definir cabeceras por archivo (`_headers`) y genera previsualizaciones por pull request; GitHub Pages es la alternativa sin cuenta adicional, pero no permite cabeceras personalizadas (verificar en su documentación vigente), lo que impide aplicar CSP completa y `frame-ancestors`. Las cuotas gratuitas de ambos deben comprobarse al decidir (R-01, D-20).

| Recurso | Cabecera | Propósito |
| --- | --- | --- |
| `index.html` y `sw.js` | `Cache-Control: no-cache` | Revalidar siempre; una versión nueva se detecta de inmediato |
| `/assets/*` | `Cache-Control: public, max-age=31536000, immutable` | Los archivos con hash nunca cambian |
| Todos | `Strict-Transport-Security: max-age=31536000; includeSubDomains` | Forzar HTTPS (RNF-SEG-04) |
| Todos | `Content-Security-Policy` (sección 3.6) | Mitigar XSS y exfiltración desde localStorage |
| Todos | `X-Content-Type-Options: nosniff` | Evitar la interpretación errónea de tipos |
| Todos | `Referrer-Policy: strict-origin-when-cross-origin` | Limitar fugas hacia enlaces externos |
| Todos | `Permissions-Policy: microphone=(self), camera=(), geolocation=()` | Permitir el micrófono solo al propio origen (RN-IAV-01) |

### 5.5 Versionado, reversión y compatibilidad de datos

- **Despliegues inmutables:** cada versión es un artefacto etiquetado. La reversión consiste en volver a publicar el artefacto o la etiqueta anterior.
- **Los datos no se revierten:** viven en el navegador de cada persona, no en el despliegue. Por eso las migraciones de esquema deben ser aditivas y compatibles hacia adelante durante, al menos, una versión (expandir y luego contraer). Si la versión N−1 encuentra un `dashnode_schema_version` mayor, entra en modo de solo lectura y avisa, sin sobrescribir (sección 3.3).
- **Service Worker (Propuesto):** actualización controlada, con un aviso «Nueva versión disponible» que recarga la aplicación, para no servir assets obsoletos indefinidamente.

### 5.6 Evolución del despliegue hacia un backend

| Fase (documento base) | Cambio de despliegue | Brechas que cierra |
| --- | --- | --- |
| 1. API REST y PostgreSQL (3 meses) | Nodo de aplicación y base de datos gestionada en plan gratuito (D-20), almacenamiento de objetos para evidencias, servicio de correo; secretos solo en el entorno del servidor; el frontend sustituye StorageAdapter por un cliente de la API | G-01 a G-04, G-06 a G-09 |
| 2. Tiempo real (1 mes) | Canal WebSocket o SSE. Queda fuera del alcance del SRS v0.2, que excluye la colaboración en tiempo real: solo si producto lo aprueba | — |
| 3. Enrutado por URL (2 semanas) | React Router v7; el hosting necesita regla de reescritura hacia `index.html` (SPA fallback) | Deep links y botón atrás (RA-04) |
| 4. IA real (1 mes) | Proxy servidor hacia el proveedor de IA en capa gratuita, con límites por usuario; voz a texto en el navegador o en el proxy; embeddings y pgvector para la búsqueda de conocimiento | G-05 |

El frontend sigue desplegándose como artefacto estático en todas las fases; lo que cambia es el conjunto de nodos que lo acompañan. Los puertos StorageAdapter y AIProvider (AD-09) y la política can() (AD-08) son los puntos de unión que evitan reescribir reducers y componentes.
