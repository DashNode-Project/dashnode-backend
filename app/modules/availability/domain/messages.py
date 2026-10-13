"""Literal user-facing messages for EP-04 and EP-05."""

AVAILABILITY_SAVED = "Disponibilidad guardada correctamente."
NO_CHANGES_TO_SAVE = "No hay cambios por guardar."
TECHNICAL_FAILURE = "No fue posible completar la operación. Intente nuevamente."
LOAD_FAILURE = "No fue posible cargar la información. Intente nuevamente."
ACCESS_DENIED = "Acceso denegado. No tiene permisos para realizar esta acción."

INVALID_TIME_INTERVAL = "El intervalo horario no es válido."
SELECT_AT_LEAST_ONE_DAY = "Seleccione al menos un día."
SELECT_AT_LEAST_ONE_PARTICIPANT = "Seleccione al menos un participante."
DURATION_WHOLE_HOURS = "La duración debe ser en horas completas."
DURATION_EXCEEDS_INTERVAL = "La duración no cabe en el intervalo seleccionado."
NO_AVAILABLE_SLOTS = "No hay horarios disponibles para los criterios seleccionados."

MEETING_CREATED = "Reunión agendada correctamente."
MEETING_SCHEDULED = "Reunión programada correctamente."
MEETING_TITLE_REQUIRED = "El título de la reunión es obligatorio."
MEETING_TYPE_REQUIRED = "Seleccione el tipo de reunión."
PROJECT_REQUIRED = "Debe seleccionar un proyecto."
PARTICIPANTS_MUST_BE_PROJECT_MEMBERS = (
    "Todos los participantes deben ser miembros del proyecto seleccionado."
)
INVALID_MEETING_LINK = "El enlace de la reunión no tiene un formato de URL válido."
PARTICIPANT_MEETING_CONFLICT = "Uno o más participantes ya tienen una reunión en ese horario."
NO_MEETINGS_TO_SHOW = "No hay reuniones para mostrar."
MEETING_CANCELLED = "Reunión cancelada correctamente."
MEETING_RESPONSE_RECORDED = "Su respuesta ha sido registrada."
MEETING_CANCELLED_CANNOT_RESPOND = "La reunión fue cancelada; no es posible responder."
MEETING_ALREADY_PAST = "No es posible responder una reunión ya realizada."
ONLY_CREATOR_CAN_CANCEL = "Solo el creador de la reunión puede cancelarla."
MEETING_CANCEL_CONFIRMATION = (
    "¿Está seguro de que desea cancelar esta reunión? Se notificará a los participantes."
)
SUMMARY_REQUIRED = "El resumen es obligatorio."
SUMMARY_TOO_LONG = "El resumen no puede superar 2000 caracteres."
INVALID_MINUTES_URL = "La URL del acta no tiene un formato válido."
MEETING_SUMMARY_SAVED = "Resumen y acta guardados correctamente."
MEETING_NOT_COMPLETED = "Solo se puede registrar resumen y acta en reuniones realizadas."
GOOGLE_CALENDAR_OPEN_FAILED = (
    "No fue posible abrir Google Calendar. Puede copiar los datos de la reunión."
)
CLIPBOARD_COPY_FAILED = "No fue posible copiar los datos. Cópielos manualmente."
MEETING_DATA_COPIED = "Datos de la reunión copiados."
MEETING_NOT_FOUND = "Reunión no encontrada."
