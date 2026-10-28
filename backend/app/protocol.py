"""Правила допуска и ранжирования, не зависящие от базы данных."""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
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
    # Время выполнения задач: при равном числе решённых задач выше тот, у кого оно меньше.
    penalty: int | None = None


def rank(entries: Sequence[Entry]) -> dict[int, int | None]:
    """Места по убыванию баллов, при равенстве — по возрастанию времени; полностью равные делят место (1, 2, 2, 4).

    Не явившиеся, дисквалифицированные и участники без баллов места не получают,
    но остаются в протоколе — ранжируются все допущенные участники.
    """
    ranked = sorted(
        (entry for entry in entries if entry.status == ResultStatus.OK and entry.score is not None),
        key=lambda entry: (-entry.score, entry.penalty or 0),
    )
    places: dict[int, int | None] = {entry.key: None for entry in entries}
    previous: tuple[Decimal, int] | None = None
    previous_place = 0
    for index, entry in enumerate(ranked, start=1):
        current = (entry.score, entry.penalty or 0)
        place = previous_place if current == previous else index
        places[entry.key] = place
        previous, previous_place = current, place
    return places


# ---------- формы протоколов (Приложение № 5 к Правилам вида спорта) ----------

PRODUCT_CRITERIA = [
    "Работоспособность прототипа", "Соответствие функциональным требованиям", "Презентация", "Технологичность", "Потенциал",
]
TWO_PLACES = Decimal("0.01")
_MARK = re.compile(r"^(\+\d{0,2}|-\d{1,2}|)$")


def normalize_mark(value: str) -> str:
    """«+» — задача решена с первой попытки, «+2» — после двух неудачных, «-3» — не решена за три попытки, пусто — не сдавалась."""
    mark = value.strip().replace("\u2212", "-").replace("\u2013", "-")
    if mark == "+0":
        mark = "+"
    if mark == "-0":
        mark = ""
    if not _MARK.match(mark):
        raise ValueError(f"Непонятная отметка по задаче: «{value}». Используйте «+», «+N», «-N» или пусто")
    return mark


def solved_count(marks: Iterable[str]) -> int:
    return sum(1 for mark in marks if mark.startswith("+"))


def judge_totals(judge_scores: Iterable[dict]) -> tuple[list[tuple[str, list[Decimal], Decimal]], list[Decimal], Decimal]:
    """Итог каждого судьи (сумма критериев), строка «ОБЩЕЕ» (среднее по критериям) и общий итог (среднее итогов)."""
    rows = []
    for item in judge_scores:
        scores = [Decimal(str(value)) for value in item["scores"]]
        rows.append((item["judge"], scores, sum(scores, Decimal("0"))))
    if not rows:
        return [], [], Decimal("0")
    overall = [
        (sum((row[1][index] for row in rows), Decimal("0")) / len(rows)).quantize(TWO_PLACES, ROUND_HALF_UP)
        for index in range(len(PRODUCT_CRITERIA))
    ]
    total = (sum((row[2] for row in rows), Decimal("0")) / len(rows)).quantize(TWO_PLACES, ROUND_HALF_UP)
    return rows, overall, total
