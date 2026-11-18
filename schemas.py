from typing import Literal, Optional
from pydantic import BaseModel, EmailStr

Role = Literal["student", "staff", "admin"]
Status = Literal["open", "in_progress", "resolved", "escalated", "closed"]
Priority = Literal["low", "medium", "high", "critical"]


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    rollNo: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AssignRequest(BaseModel):
    staffId: str
    priority: Optional[Priority] = None
    dueHours: Optional[int] = None


class StatusRequest(BaseModel):
    status: Status


class CommentRequest(BaseModel):
    message: str
    isInternal: bool = False
