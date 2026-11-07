"""Literal user-facing messages for EP-11 Issues and Evidences.

@sad AD-08, RNF-SEG-07
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
"""

# Validation error messages
TITLE_REQUIRED = "El título es obligatorio."
TITLE_TOO_LONG = "El título no puede superar 100 caracteres."
DESCRIPTION_TOO_LONG = "La descripción no puede superar 5000 caracteres."
SEVERITY_REQUIRED = "Debe seleccionar la severidad."
TYPE_REQUIRED = "Debe seleccionar el tipo."

# File & Evidence validation error messages
UNSUPPORTED_FORMAT = "Formato de archivo no admitido."
FILE_TOO_LARGE = "El archivo excede el tamaño máximo permitido."
VIDEO_TOO_LONG = "El video no puede superar los 60 segundos de duración."
DUPLICATE_EVIDENCE = "Ya existe una evidencia idéntica asociada a este issue."
EVIDENCE_TITLE_TOO_LONG = "El título de la evidencia no puede superar 255 caracteres."

# Operation success messages
ISSUE_CREATED = "Issue creado correctamente."
EVIDENCE_ATTACHED = "Evidencia adjuntada correctamente."

# Empty state messages
NO_ISSUES_FOUND = "El proyecto no tiene issues."
NO_FILTERED_ISSUES = "No se encontraron issues con los filtros aplicados."

# Technical failure messages
GENERIC_ERROR = "No fue posible completar la operación. Intente nuevamente."
NOT_MEMBER_ERROR = "El usuario debe ser miembro activo del proyecto."
ISSUE_NOT_FOUND = "El issue solicitado no existe."
EVIDENCE_NOT_FOUND = "La evidencia solicitada no existe."
SIGNATURE_INVALID_OR_EXPIRED = "El enlace de descarga ha expirado o es inválido."
