"""SQLAlchemy database models."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON
from database import Base


def _now():
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Test(Base):
    __tablename__ = "tests"

    id          = Column(String(16),  primary_key=True, default=new_id)
    name        = Column(String(200), nullable=False)
    athlete_name= Column(String(200), nullable=True)
    date        = Column(String(10),  nullable=True)   # "YYYY-MM-DD"
    sport       = Column(String(30),  nullable=False, default="cycling")
    notes       = Column(Text,        nullable=True,  default="")
    steps       = Column(JSON,        nullable=False)  # list[{intensity, lactate, hr}]
    results     = Column(JSON,        nullable=True)   # {lt1, lt2, lt1Method, lt2Method}
    source      = Column(String(20),  nullable=False, default="web")  # web | dex | api
    created_at  = Column(DateTime(timezone=True), default=_now)
    updated_at  = Column(DateTime(timezone=True), default=_now, onupdate=_now)
