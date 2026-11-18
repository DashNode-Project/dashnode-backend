"""UtcDateTime type adapter."""

from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.shared.infrastructure.types import UtcDateTime


class Base(DeclarativeBase):
    pass


class Row(Base):
    __tablename__ = "utc_probe"
    id: Mapped[int] = mapped_column(primary_key=True)
    when: Mapped[datetime] = mapped_column(UtcDateTime())


def test_utc_datetime_roundtrip_aware_value() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    bogota = timezone(timedelta(hours=-5))
    aware = datetime(2026, 11, 18, 9, 0, tzinfo=bogota)
    with Session(engine) as session:
        session.add(Row(id=1, when=aware))
        session.commit()
        loaded = session.get(Row, 1)
        assert loaded is not None
        assert loaded.when.tzinfo is not None
        assert loaded.when.astimezone(UTC).hour == 14

    col = UtcDateTime()
    out = col.process_result_value(aware, dialect=engine.dialect)
    assert out is not None
    assert out.tzinfo == UTC
