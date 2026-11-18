"""Shared helpers: activity log, notifications, escalation."""
import datetime as dt
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import ActivityLog, Notification, Complaint, Category, Escalation, User, now

# Escalation threshold = category SLA hours * multiplier
PRIORITY_FACTOR = {"critical": 0.25, "high": 0.5, "medium": 1.0, "low": 2.0}


def log(db: Session, complaint_id: str, actor_id, action: str, frm=None, to=None):
    db.add(ActivityLog(complaint_id=complaint_id, actor_id=actor_id, action=action, from_value=frm, to_value=to))


def notify(db: Session, user_id: str, complaint_id, type_: str, message: str):
    db.add(Notification(user_id=user_id, complaint_id=complaint_id, type=type_, channel="in_app", message=message))
    # Email stub: swap for smtplib / SendGrid in production
    user = db.get(User, user_id)
    if user:
        print(f"[EMAIL -> {user.email}] {message}")


def run_escalation(db: Session, threshold_override_hours: float | None = None) -> list[str]:
    """Escalate overdue complaints. Returns list of escalated complaint ids."""
    escalated = []
    admin = db.scalar(select(User).where(User.role == "admin"))
    active = db.scalars(
        select(Complaint).where(Complaint.status.in_(["open", "in_progress"]), Complaint.escalation_level == 0)
    ).all()
    for c in active:
        cat = db.get(Category, c.category_id)
        limit = (
            threshold_override_hours
            if threshold_override_hours is not None
            else (cat.sla_hours if cat else 48) * PRIORITY_FACTOR.get(c.priority, 1.0)
        )
        age_hours = (now() - c.created_at).total_seconds() / 3600
        if age_hours >= limit:
            old = c.status
            c.status = "escalated"
            c.escalation_level = 1
            reason = f"Unresolved for {age_hours:.1f}h (limit {limit:.1f}h)"
            db.add(Escalation(complaint_id=c.id, level=1, escalated_to=admin.id if admin else None, reason=reason))
            log(db, c.id, None, "escalated", old, "escalated")
            if admin:
                notify(db, admin.id, c.id, "escalated", f"Complaint '{c.title}' escalated: {reason}")
            notify(db, c.created_by, c.id, "escalated", f"Your complaint '{c.title}' has been escalated.")
            escalated.append(c.id)
    db.commit()
    return escalated
