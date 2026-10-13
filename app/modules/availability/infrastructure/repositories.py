"""SQLAlchemy repository implementation for Availability module."""

import json

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.availability.domain.entities import Meeting, TimeSlot, UserAvailability
from app.modules.availability.domain.ports import AvailabilityRepository
from app.modules.availability.infrastructure.models import (
    MeetingModel,
    MeetingParticipantModel,
    UserAvailabilityModel,
)


def _slots_to_json(slots: dict[str, list[TimeSlot]]) -> str:
    serialized: dict[str, list[dict[str, str]]] = {}
    for day, slot_list in slots.items():
        serialized[day] = [{"start": s.start, "end": s.end} for s in slot_list]
    return json.dumps(serialized)


def _json_to_slots(raw_json: str) -> dict[str, list[TimeSlot]]:
    try:
        data = json.loads(raw_json)
        result: dict[str, list[TimeSlot]] = {}
        for day, slot_list in data.items():
            result[day] = [TimeSlot(start=s["start"], end=s["end"]) for s in slot_list]
        return result
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def _to_entity(model: UserAvailabilityModel) -> UserAvailability:
    return UserAvailability(
        id=model.id,
        user_id=model.user_id,
        week_start_date=model.week_start_date,
        slots=_json_to_slots(model.slots_json),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _meeting_to_entity(model: MeetingModel, participant_ids: list[str]) -> Meeting:
    return Meeting(
        id=model.id,
        project_id=model.project_id,
        title=model.title,
        description=model.description,
        date=model.date,
        start_time=model.start_time,
        end_time=model.end_time,
        duration=model.duration,
        link=model.link,
        status=model.status,
        creator_id=model.creator_id,
        participant_ids=participant_ids,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyAvailabilityRepository(AvailabilityRepository):
    """SQLAlchemy implementation of AvailabilityRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_availability(self, user_id: str, week_start_date: str) -> UserAvailability | None:
        model = self._session.scalar(
            select(UserAvailabilityModel).where(
                UserAvailabilityModel.user_id == user_id,
                UserAvailabilityModel.week_start_date == week_start_date,
            )
        )
        return _to_entity(model) if model else None

    def get_latest_availability(
        self, user_id: str, before_or_on_week: str
    ) -> UserAvailability | None:
        model = self._session.scalar(
            select(UserAvailabilityModel)
            .where(
                UserAvailabilityModel.user_id == user_id,
                UserAvailabilityModel.week_start_date <= before_or_on_week,
            )
            .order_by(UserAvailabilityModel.week_start_date.desc())
            .limit(1)
        )
        return _to_entity(model) if model else None

    def save_user_availability(self, availability: UserAvailability) -> None:
        existing = self._session.scalar(
            select(UserAvailabilityModel).where(
                UserAvailabilityModel.user_id == availability.user_id,
                UserAvailabilityModel.week_start_date == availability.week_start_date,
            )
        )
        slots_str = _slots_to_json(availability.slots)
        if existing:
            existing.slots_json = slots_str
            existing.updated_at = availability.updated_at
        else:
            new_model = UserAvailabilityModel(
                id=availability.id,
                user_id=availability.user_id,
                week_start_date=availability.week_start_date,
                slots_json=slots_str,
                created_at=availability.created_at,
                updated_at=availability.updated_at,
            )
            self._session.add(new_model)

    def list_availabilities_for_users(
        self, user_ids: list[str], week_start_date: str
    ) -> dict[str, UserAvailability]:
        if not user_ids:
            return {}
        models = self._session.scalars(
            select(UserAvailabilityModel).where(
                UserAvailabilityModel.user_id.in_(user_ids),
                UserAvailabilityModel.week_start_date == week_start_date,
            )
        ).all()
        return {m.user_id: _to_entity(m) for m in models}

    def get_meetings_for_participants(
        self, user_ids: list[str], start_date: str, end_date: str
    ) -> list[Meeting]:
        if not user_ids:
            return []
        query = (
            select(MeetingModel)
            .outerjoin(
                MeetingParticipantModel,
                MeetingModel.id == MeetingParticipantModel.meeting_id,
            )
            .where(
                or_(
                    MeetingParticipantModel.user_id.in_(user_ids),
                    MeetingModel.creator_id.in_(user_ids),
                ),
                MeetingModel.date >= start_date,
                MeetingModel.date <= end_date,
                MeetingModel.status == "scheduled",
            )
            .distinct()
        )
        meetings = self._session.scalars(query).all()
        result: list[Meeting] = []
        for m in meetings:
            p_ids = self._session.scalars(
                select(MeetingParticipantModel.user_id).where(
                    MeetingParticipantModel.meeting_id == m.id
                )
            ).all()
            result.append(_meeting_to_entity(m, list(p_ids)))
        return result

    def save_meeting(self, meeting: Meeting) -> None:
        meeting_model = MeetingModel(
            id=meeting.id,
            project_id=meeting.project_id,
            title=meeting.title,
            description=meeting.description,
            date=meeting.date,
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            duration=meeting.duration,
            link=meeting.link,
            status=meeting.status,
            creator_id=meeting.creator_id,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
        )
        self._session.add(meeting_model)
        for uid in meeting.participant_ids:
            self._session.add(MeetingParticipantModel(meeting_id=meeting.id, user_id=uid))
