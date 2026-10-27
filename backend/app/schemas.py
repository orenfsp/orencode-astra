from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models import CompetitionStatus


class CompetitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    discipline: str
    date: date
    location: str
    status: CompetitionStatus
