"""Horário comercial (spec §4). Define se o agente tenta agendamento (fora-horário)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .config import settings

# weekday(): 0=seg ... 6=dom. (abre, fecha) em horas; None = fechado.
_HOURS = {
    0: (9, 18),
    1: (9, 18),
    2: (9, 18),
    3: (9, 18),
    4: (9, 18),
    5: (9, 13),  # sáb
    6: None,     # dom
}


def now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone))


def is_business_hours(dt: datetime | None = None) -> bool:
    dt = dt or now_local()
    window = _HOURS.get(dt.weekday())
    if not window:
        return False
    return window[0] <= dt.hour < window[1]
