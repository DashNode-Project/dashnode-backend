"""SQLAlchemy repository implementation for Availability module."""

import json

from sqlalchemy import delete, or_, select
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
        type=model.type or "General",
        summary=model.summary,
        minutes_url=model.minutes_url,
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
                MeetingModel.status != "cancelled",
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
            type=meeting.type,
            description=meeting.description,
            date=meeting.date,
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            duration=meeting.duration,
            link=meeting.link,
            status=meeting.status,
            summary=meeting.summary,
            minutes_url=meeting.minutes_url,
            creator_id=meeting.creator_id,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
        )
        self._session.add(meeting_model)
        for uid in meeting.participant_ids:
            self._session.add(
                MeetingParticipantModel(meeting_id=meeting.id, user_id=uid, response="pendiente")
            )

    def get_meeting_by_id(self, meeting_id: str) -> Meeting | None:
        model = self._session.scalar(select(MeetingModel).where(MeetingModel.id == meeting_id))
        if model is None:
            return None
        p_ids = self._session.scalars(
            select(MeetingParticipantModel.user_id).where(
                MeetingParticipantModel.meeting_id == model.id
            )
        ).all()
        return _meeting_to_entity(model, list(p_ids))

    def list_all_meetings(self) -> list[Meeting]:
        models = self._session.scalars(
            select(MeetingModel).order_by(MeetingModel.date.asc(), MeetingModel.start_time.asc())
        ).all()
        result: list[Meeting] = []
        for m in models:
            p_ids = self._session.scalars(
                select(MeetingParticipantModel.user_id).where(
                    MeetingParticipantModel.meeting_id == m.id
                )
            ).all()
            result.append(_meeting_to_entity(m, list(p_ids)))
        return result

    def get_meetings_by_projects(self, project_ids: list[str]) -> list[Meeting]:
        if not project_ids:
            return []
        models = self._session.scalars(
            select(MeetingModel)
            .where(MeetingModel.project_id.in_(project_ids))
            .order_by(MeetingModel.date.asc(), MeetingModel.start_time.asc())
        ).all()
        result: list[Meeting] = []
        for m in models:
            p_ids = self._session.scalars(
                select(MeetingParticipantModel.user_id).where(
                    MeetingParticipantModel.meeting_id == m.id
                )
            ).all()
            result.append(_meeting_to_entity(m, list(p_ids)))
        return result

    def get_meetings_by_creator(self, creator_id: str) -> list[Meeting]:
        models = self._session.scalars(
            select(MeetingModel)
            .where(MeetingModel.creator_id == creator_id)
            .order_by(MeetingModel.date.asc(), MeetingModel.start_time.asc())
        ).all()
        result: list[Meeting] = []
        for m in models:
            p_ids = self._session.scalars(
                select(MeetingParticipantModel.user_id).where(
                    MeetingParticipantModel.meeting_id == m.id
                )
            ).all()
            result.append(_meeting_to_entity(m, list(p_ids)))
        return result

    def update_meeting(self, meeting: Meeting) -> None:
        model = self._session.scalar(select(MeetingModel).where(MeetingModel.id == meeting.id))
        if model is not None:
            model.title = meeting.title
            model.type = meeting.type
            model.description = meeting.description
            model.date = meeting.date
            model.start_time = meeting.start_time
            model.end_time = meeting.end_time
            model.duration = meeting.duration
            model.link = meeting.link
            model.status = meeting.status
            model.summary = meeting.summary
            model.minutes_url = meeting.minutes_url
            model.updated_at = meeting.updated_at

    def replace_meeting_participants(self, meeting_id: str, participant_ids: list[str]) -> None:
        existing_responses = self.get_participant_responses(meeting_id)
        self._session.execute(
            delete(MeetingParticipantModel).where(MeetingParticipantModel.meeting_id == meeting_id)
        )
        for uid in participant_ids:
            self._session.add(
                MeetingParticipantModel(
                    meeting_id=meeting_id,
                    user_id=uid,
                    response=existing_responses.get(uid, "pendiente"),
                )
            )

    def delete_meeting(self, meeting_id: str) -> None:
        self._session.execute(
            delete(MeetingParticipantModel).where(MeetingParticipantModel.meeting_id == meeting_id)
        )
        self._session.execute(delete(MeetingModel).where(MeetingModel.id == meeting_id))

    def cancel_scheduled_meetings_for_project(self, project_id: str, when: object) -> None:
        from datetime import datetime

        from sqlalchemy import update

        assert isinstance(when, datetime)
        self._session.execute(
            update(MeetingModel)
            .where(
                MeetingModel.project_id == project_id,
                MeetingModel.status == "scheduled",
            )
            .values(status="cancelled", updated_at=when)
        )

    def get_participant_responses(self, meeting_id: str) -> dict[str, str]:
        records = self._session.execute(
            select(MeetingParticipantModel.user_id, MeetingParticipantModel.response).where(
                MeetingParticipantModel.meeting_id == meeting_id
            )
        ).all()
        return {r[0]: r[1] for r in records}

    def update_participant_response(self, meeting_id: str, user_id: str, response: str) -> None:
        participant = self._session.scalar(
            select(MeetingParticipantModel).where(
                MeetingParticipantModel.meeting_id == meeting_id,
                MeetingParticipantModel.user_id == user_id,
            )
        )
        if participant is not None:
            participant.response = response

    def check_concurrent_meeting(
        self,
        participant_ids: list[str],
        date: str,
        start_time: str,
        end_time: str,
        exclude_meeting_id: str | None = None,
    ) -> bool:
        if not participant_ids:
            return False
        # Overlapping condition: meeting.start_time < end_time AND meeting.end_time > start_time
        query = (
            select(MeetingModel.id)
            .outerjoin(
                MeetingParticipantModel,
                MeetingModel.id == MeetingParticipantModel.meeting_id,
            )
            .where(
                MeetingModel.date == date,
                MeetingModel.status != "cancelled",
                MeetingModel.start_time < end_time,
                MeetingModel.end_time > start_time,
                or_(
                    MeetingParticipantModel.user_id.in_(participant_ids),
                    MeetingModel.creator_id.in_(participant_ids),
                ),
            )
        )
        if exclude_meeting_id:
            query = query.where(MeetingModel.id != exclude_meeting_id)
        existing = self._session.scalar(query.limit(1))
        return existing is not None
