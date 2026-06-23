"""Agenda GHL (caminho fora-horário): free-slots → book na agenda dos negociadores.

Spec §5: dentro do horário o agente PARA antes de agendar; fora do horário tenta
o agendamento prévio nas agendas de Adriano/Dário.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..ghl.client import get_client
from ..logging import get_logger

log = get_logger("tools.calendar")

_NEGOCIADOR_CALENDARS = [c for c in (settings.calendar_adriano, settings.calendar_dario) if c]


@dataclass
class Slot:
    calendar_id: str
    start_iso: str

    def label_pt(self) -> str:
        dt = datetime.fromisoformat(self.start_iso)
        return dt.strftime("%d/%m %H:%M")


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


async def propose_slots(*, janela_dias: int = 7, limit: int = 3) -> list[Slot]:
    if not _NEGOCIADOR_CALENDARS:
        return []
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=janela_dias)
    slots: list[Slot] = []
    for cal in _NEGOCIADOR_CALENDARS:
        try:
            d = await get_client().get(
                f"/calendars/{cal}/free-slots",
                operation="free_slots",
                params={"startDate": _ms(now), "endDate": _ms(end)},
            )
        except Exception as exc:
            log.warning("free_slots_failed", calendar=cal, error=str(exc))
            continue
        for day in (d.get("dates") or d.values() if isinstance(d, dict) else []):
            for s in (day.get("slots", []) if isinstance(day, dict) else []):
                slots.append(Slot(calendar_id=cal, start_iso=s))
                if len(slots) >= limit:
                    return slots
    return slots[:limit]


async def book_appointment(*, contact_id: str, slot: Slot, lead_name: str, modelo: str) -> dict:
    start = datetime.fromisoformat(slot.start_iso)
    end = start + timedelta(minutes=settings.ghl_appointment_duration_min)
    payload = {
        "calendarId": slot.calendar_id,
        "locationId": settings.ghl_location_id,
        "contactId": contact_id,
        "startTime": slot.start_iso,
        "endTime": end.isoformat(),
        "title": f"Avaliação Vaapty — {lead_name or 'Lead'} — {modelo or 'veículo'}",
        "appointmentStatus": "confirmed",
    }
    return await get_client().post(
        "/calendars/events/appointments", operation="book_appointment", json=payload
    )
