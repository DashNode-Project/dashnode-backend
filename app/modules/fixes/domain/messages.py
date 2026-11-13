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
