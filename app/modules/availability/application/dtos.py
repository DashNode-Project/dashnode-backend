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
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    date: str = Field(description="Fecha en formato YYYY-MM-DD")
    start_time: str = Field(description="Hora de inicio (HH:MM)")
    end_time: str = Field(description="Hora de fin (HH:MM)")
    duration: int = Field(ge=1, description="Duración en minutos")
    link: str | None = None
    participant_ids: list[str] = Field(min_length=1)


class MeetingDTO(BaseModel):
    id: str
    project_id: str | None
    title: str
    description: str
    date: str
    start_time: str
    end_time: str
    duration: int
    link: str | None
    status: str
    creator_id: str
    participant_ids: list[str]


class MessageResponse(BaseModel):
    message: str
