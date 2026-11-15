"""Literal user-facing messages for EP-11 Issues and Evidences.

@sad AD-08, RNF-SEG-07
@origin [User Stories HU_DN_07_97 .. HU_DN_07_105]
"""

# Validation error messages
TITLE_REQUIRED = "El título es obligatorio."
TITLE_TOO_LONG = "El título no puede superar 100 caracteres."
DESCRIPTION_TOO_LONG = "La descripción no puede superar 5000 caracteres."
SEVERITY_REQUIRED = "Debe seleccionar la severidad."
TYPE_REQUIRED = "Debe seleccionar el tipo."
RESOLUTION_NOTE_REQUIRED = "Debe registrar la nota de resolución."
RESOLUTION_NOTE_TOO_LONG = "La nota de resolución no puede superar 2000 caracteres."
ISSUE_NOT_OPEN = "Solo los issues abiertos pueden resolverse."
ISSUE_NOT_RESOLVED = "Solo los issues resueltos pueden cerrarse."
ASSIGN_DEVELOPER_ONLY = "Solo se pueden asignar desarrolladores miembros del proyecto."
TASK_TARGET_STATUS_INVALID = "El estado seleccionado para restaurar la tarea no es válido."

# Authorization error messages
ASSIGN_FORBIDDEN = "Acceso denegado. Solo Administrador o Gerente pueden asignar issues."
CLOSE_FORBIDDEN = "Acceso denegado. Solo Administrador o Gerente pueden cerrar issues."
FIX_REPORT_OWN_TASKS_ONLY = "Acceso denegado. Solo puede reportar fixes sobre sus propias tareas."

# File & Evidence validation error messages
UNSUPPORTED_FORMAT = "Formato de archivo no admitido."
FILE_TOO_LARGE = "El archivo excede el tamaño máximo permitido."
VIDEO_TOO_LONG = "El video no puede superar los 60 segundos de duración."
DUPLICATE_EVIDENCE = "Ya existe una evidencia idéntica asociada a este issue."
EVIDENCE_TITLE_TOO_LONG = "El título de la evidencia no puede superar 255 caracteres."

# Operation success messages
ISSUE_CREATED = "Issue creado correctamente."
EVIDENCE_ATTACHED = "Evidencia adjuntada correctamente."
ISSUE_ASSIGNED = "Issue asignado correctamente."
ISSUE_RESOLVED = "Issue resuelto correctamente."
ISSUE_CLOSED = "Issue cerrado correctamente."
TASK_FIX_REPORTED = "Fix reportado. La tarea pasó a estado Corrección."
TASK_UNLINKED_AND_UPDATED = "La tarea fue desvinculada y su estado se actualizó."

# Linked task status warnings
TASK_OTHER_OPEN_ISSUES = (
    "La tarea tiene otros issues abiertos. Permanecerá en Corrección hasta resolverlos."
)

# Concurrency / Conflict error messages
OPTIMISTIC_LOCK_CONFLICT = (
    "El issue fue modificado por otro usuario. Recargue e intente nuevamente."
)

# Empty state messages
NO_ISSUES_FOUND = "El proyecto no tiene issues."
NO_FILTERED_ISSUES = "No se encontraron issues con los filtros aplicados."

# Technical failure messages
GENERIC_ERROR = "No fue posible completar la operación. Intente nuevamente."
NOT_MEMBER_ERROR = "El usuario debe ser miembro activo del proyecto."
ISSUE_NOT_FOUND = "El issue solicitado no existe."
TASK_NOT_FOUND = "La tarea solicitada no existe."
EVIDENCE_NOT_FOUND = "La evidencia solicitada no existe."
SIGNATURE_INVALID_OR_EXPIRED = "El enlace de descarga ha expirado o es inválido."

# EP-12 AI visual evidence analysis messages (HU_DN_07_106 .. HU_DN_07_110)
AI_CONFIRMATION_REQUIRED = (
    "Debe confirmar que la evidencia no contiene contraseñas, tokens ni datos personales."
)
NO_EVIDENCE_FOR_ANALYSIS = "El issue no tiene evidencia para analizar."
AI_UNSUPPORTED_FORMAT = "El formato de la evidencia no es admitido para el análisis."
DAILY_LIMIT_REACHED = "Alcanzó el límite diario de solicitudes de IA."
AI_ANALYSIS_REQUESTED = "Análisis solicitado. Procesando…"
AI_ANALYSIS_REUSED = "Ya existe un análisis de esta evidencia."
AI_ANALYSIS_DELETED = "Respuesta de IA eliminada correctamente."
AI_DELETE_FORBIDDEN = "No tiene permiso para eliminar esta respuesta."
AI_DELETE_PROCESSING_FORBIDDEN = (
    "No es posible eliminar un análisis mientras está en procesamiento."
)
AI_ANALYSIS_NOT_FOUND = "La respuesta no existe o ya fue eliminada."
AI_NO_RESPONSES = "Este issue no tiene respuestas de IA."
AI_UNVERIFIED_LABEL = "Sugerencia generada por IA no verificada"
AI_INSUFFICIENT_CONTEXT = "No hay contexto suficiente para proponer una solución."
EVIDENCE_LOAD_ERROR = "No fue posible cargar la evidencia."
AI_PROVIDER_ERROR = "El servicio de IA no pudo procesar la solicitud."
AI_OUTPUT_INVALID = "El servicio de IA no pudo procesar la solicitud."
AI_TIMEOUT = "El análisis excedió el tiempo de espera."
AI_QUOTA_EXHAUSTED = "Se agotó la cuota gratuita del servicio de IA. Intente más tarde."
AI_TECHNICAL_LOAD_ERROR = "No fue posible cargar la información. Intente nuevamente."

# EP-12 Human validation of AI analysis messages (HU_DN_07_111 .. HU_DN_07_113)
AI_VALIDATE_SUCCESS = "Respuesta de IA validada correctamente."
AI_REJECT_SUCCESS = "Respuesta de IA rechazada."
AI_VALIDATE_FORBIDDEN = "Solo un Administrador o Gerente puede validar respuestas de IA."
AI_REJECT_FORBIDDEN = "Solo un Administrador o Gerente puede rechazar respuestas de IA."
AI_VALIDATE_INVALID_STATE = "Solo se pueden validar respuestas pendientes."
AI_REJECT_INVALID_STATE = "La respuesta ya fue rechazada."
AI_HUMAN_VALIDATION_NOTICE = (
    "Esta propuesta de IA no ha sido validada. Requiere validación de un Administrador o Gerente"
    " antes de actuar."
)
