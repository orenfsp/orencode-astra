"""Правила допуска и ранжирования, не зависящие от базы данных."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol as TypingProtocol

from app.application_models import ResultStatus


def competition_age(birth_date: date, competition_date: date) -> int:
    """Возраст спортсмена для допуска: сколько лет исполняется в календарном году соревнования.

    По практике правил вида спорта возраст определяется годом рождения, а не точной датой,
    поэтому спортсмен 2012 г. р. в 2026 году выступает как 14-летний весь сезон.
    """
    return competition_date.year - birth_date.year


class _Group(TypingProtocol):
    id: int
    min_age: int
    max_age: int | None


def fitting_groups(age: int, groups: Iterable[_Group]) -> list[_Group]:
    return [group for group in groups if group.min_age <= age and (group.max_age is None or age <= group.max_age)]


@dataclass
class Entry:
    key: int
    score: Decimal | None
    status: ResultStatus


def rank(entries: Sequence[Entry]) -> dict[int, int | None]:
    """Места по убыванию баллов; равные баллы делят место (1, 2, 2, 4).

    Не явившиеся, дисквалифицированные и участники без баллов места не получают,
    но остаются в протоколе — ранжируются все допущенные участники.
    """
    ranked = sorted((entry for entry in entries if entry.status == ResultStatus.OK and entry.score is not None), key=lambda entry: entry.score, reverse=True)
    places: dict[int, int | None] = {entry.key: None for entry in entries}
    previous_score: Decimal | None = None
    previous_place = 0
    for index, entry in enumerate(ranked, start=1):
        place = previous_place if entry.score == previous_score else index
        places[entry.key] = place
        previous_score, previous_place = entry.score, place
    return places
