"""Data Transfer Objects for Availability and Meetings."""

from pydantic import BaseModel, Field


class TimeSlotDTO(BaseModel):
    start: str = Field(description="Hora de inicio en formato HH:MM (24h)")
    end: str = Field(description="Hora de fin en formato HH:MM (24h)")


class SaveAvailabilityCommand(BaseModel):
    week_start_date: str = Field(description="Fecha de inicio de la semana (Lunes YYYY-MM-DD)")
    slots: dict[str, list[TimeSlotDTO]] = Field(
        description="Mapeo de día (monday..sunday) a lista de franjas horarias"
    )


class UserAvailabilityResponse(BaseModel):
    week_start_date: str
    slots: dict[str, list[TimeSlotDTO]]
    is_inherited: bool = Field(
        default=False,
        description="Indica si la disponibilidad fue heredada de semanas anteriores",
    )


class TeamUserAvailabilityDTO(BaseModel):
    user_id: str
    name: str
    email: str
    role: str
    slots: dict[str, list[TimeSlotDTO]]


class TeamAvailabilityResponse(BaseModel):
    week_start_date: str
    users: list[TeamUserAvailabilityDTO]


class SearchMeetingSlotsCommand(BaseModel):
    interval_start: str = Field(description="Hora de inicio en formato 24h (HH:MM)")
    interval_end: str = Field(description="Hora de fin en formato 24h (HH:MM)")
    days: list[str] = Field(description="Lista de días de la semana (monday..sunday)")
    participant_ids: list[str] = Field(description="IDs de participantes seleccionados")
    duration_hours: int = Field(ge=1, description="Duración en horas enteras")
    week_start_date: str | None = Field(
        default=None, description="Lunes de la semana a consultar (opcional)"
    )


class DayAvailableSlotsDTO(BaseModel):
    day: str
    date: str
    slots: list[TimeSlotDTO]


class SearchMeetingSlotsResponse(BaseModel):
    results: list[DayAvailableSlotsDTO]


class CreateMeetingCommand(BaseModel):
    project_id: str | None = None
    title: str = Field(default="")
    type: str = Field(default="")
    description: str = Field(default="", max_length=1000)
    date: str = Field(description="Fecha en formato YYYY-MM-DD")
    start_time: str = Field(description="Hora de inicio (HH:MM)")
    end_time: str = Field(description="Hora de fin (HH:MM)")
    duration: int = Field(ge=1, description="Duración en minutos")
    link: str | None = None
    participant_ids: list[str] = Field(default_factory=list)


class ParticipantDTO(BaseModel):
    user_id: str
    name: str = ""
    email: str = ""
    role: str = ""
    response: str = "pendiente"  # 'pendiente', 'aceptada', 'rechazada'


class MeetingDTO(BaseModel):
    id: str
    project_id: str | None = None
    project_name: str | None = None
    title: str
    type: str = "General"
    description: str = ""
    date: str
    start_time: str
    end_time: str
    duration: int
    link: str | None = None
    status: str = "scheduled"  # 'scheduled', 'completed', 'cancelled'
    creator_id: str
    creator_name: str | None = None
    participant_ids: list[str] = Field(default_factory=list)
    participants: list[ParticipantDTO] = Field(default_factory=list)
    summary: str | None = None
    minutes_url: str | None = None


class RespondMeetingCommand(BaseModel):
    response: str = Field(description="Respuesta a la reunión ('aceptada' | 'rechazada')")


class UpdateMeetingSummaryCommand(BaseModel):
    summary: str | None = Field(default=None)
    minutes_url: str | None = Field(default=None)


class UpdateMeetingCommand(BaseModel):
    title: str | None = Field(default=None, description="Nuevo título de la reunión")
    link: str | None = Field(default=None, description="Nuevo enlace de la reunión")
    participant_ids: list[str] | None = Field(
        default=None, description="Lista actualizada de participantes"
    )


class ProjectManagedDTO(BaseModel):
    id: str
    name: str
    manager_id: str | None = None
    meeting_link: str | None = None
    member_ids: list[str] = Field(default_factory=list)


class MessageResponse(BaseModel):
    message: str
