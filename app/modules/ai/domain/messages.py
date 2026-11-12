"""Literal user-facing messages for the AI assistant (EP-10)."""

EMPTY_AUDIO = "No se detectó audio. Intente nuevamente."
VOICE_NOT_UNDERSTOOD = (
    "No pude interpretar el audio como una consulta sobre DashNode "
    "(proyectos, HUs, tareas o sprints). Hable con claridad y formule su pregunta en voz alta."
)
AUDIO_TOO_LONG = "La grabación excede la duración máxima permitida."
AI_PROCESSING_ERROR = "El asistente no pudo procesar la consulta."
AI_REQUEST_TIMEOUT = (
    "La consulta tardó demasiado en procesarse. Intente de nuevo con una pregunta más concreta."
)
AI_GEMINI_UNAVAILABLE = (
    "El servicio de IA no respondió a tiempo. Intente nuevamente en unos momentos."
)
FREE_QUOTA_EXHAUSTED = "Se agotó la cuota gratuita del servicio de IA. Intente más tarde."
TECHNICAL_FAILURE = "No fue posible completar la operación. Intente nuevamente."
LOAD_FAILURE = "No fue posible cargar la información. Intente nuevamente."
