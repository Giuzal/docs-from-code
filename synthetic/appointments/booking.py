"""Booking, moving and cancelling clinic visits."""

from dataclasses import dataclass
from datetime import datetime, timedelta

CANCEL_WINDOW = timedelta(hours=24)


class TooLateToCancel(Exception):
    pass


@dataclass
class Appointment:
    id: str
    patient_id: str
    starts_at: datetime
    cancelled: bool = False


def cancel(appointment: Appointment, now: datetime) -> Appointment:
    """Cancel a visit.

    Patients can cancel up to 48 hours before the visit.
    """
    if appointment.starts_at - now < CANCEL_WINDOW:
        raise TooLateToCancel(appointment.id)
    appointment.cancelled = True
    return appointment
