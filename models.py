import uuid
import datetime as dt
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def row(o, exclude=()):
    """Serialize a model instance to a dict."""
    return {c.name: getattr(o, c.name) for c in o.__table__.columns if c.name not in exclude}


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    head_id: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, default="")


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"))
    sla_hours: Mapped[int] = mapped_column(Integer, default=48)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="student")  # student | staff | admin
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    roll_no: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Complaint(Base):
    __tablename__ = "complaints"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String, default="open")  # open|in_progress|resolved|escalated|closed
    priority: Mapped[str] = mapped_column(String, default="medium")  # low|medium|high|critical
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    upvotes: Mapped[int] = mapped_column(Integer, default=0)
    is_duplicate_of: Mapped[str | None] = mapped_column(String, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    complaint_id: Mapped[str] = mapped_column(ForeignKey("complaints.id"))
    assigned_to: Mapped[str] = mapped_column(ForeignKey("users.id"))
    assigned_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    complaint_id: Mapped[str] = mapped_column(ForeignKey("complaints.id"))
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    message: Mapped[str] = mapped_column(Text)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    complaint_id: Mapped[str] = mapped_column(ForeignKey("complaints.id"))
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String)
    from_value: Mapped[str | None] = mapped_column(String, nullable=True)
    to_value: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Escalation(Base):
    __tablename__ = "escalations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    complaint_id: Mapped[str] = mapped_column(ForeignKey("complaints.id"))
    level: Mapped[int] = mapped_column(Integer, default=1)
    escalated_to: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(String)
    triggered_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    complaint_id: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String)  # assigned|status_update|escalated|comment
    channel: Mapped[str] = mapped_column(String, default="in_app")
    message: Mapped[str] = mapped_column(String)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Upvote(Base):
    __tablename__ = "upvotes"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    complaint_id: Mapped[str] = mapped_column(ForeignKey("complaints.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
