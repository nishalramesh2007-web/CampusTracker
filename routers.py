import os
import shutil
import datetime as dt
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import create_token, current_user, hash_password, require_roles, verify_password
from .database import get_db
from .models import (ActivityLog, Assignment, Category, Comment, Complaint, Department,
                     Notification, Upvote, User, now, row, uid)
from .schemas import AssignRequest, CommentRequest, LoginRequest, RegisterRequest, StatusRequest
from .services import log, notify, run_escalation

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter()


def user_out(u: User):
    return row(u, exclude=("password_hash",))


def ok(data):
    return {"success": True, "data": data}


# ---------------------------------------------------------------- Auth
@router.post("/auth/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == req.email)):
        raise HTTPException(400, "Email already registered")
    u = User(name=req.name, email=req.email, password_hash=hash_password(req.password),
             role="student", roll_no=req.rollNo)
    db.add(u)
    db.commit()
    return ok({"token": create_token(u), "user": user_out(u)})


@router.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == req.email))
    if not u or not verify_password(req.password, u.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return ok({"token": create_token(u), "user": user_out(u)})


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return ok(user_out(user))


# ---------------------------------------------------------------- Meta
@router.get("/meta/categories")
def categories(db: Session = Depends(get_db)):
    return ok([row(c) for c in db.scalars(select(Category))])


@router.get("/meta/departments")
def departments(db: Session = Depends(get_db)):
    return ok([row(d) for d in db.scalars(select(Department))])


@router.get("/meta/staff")
def staff(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    return ok([user_out(u) for u in db.scalars(select(User).where(User.role == "staff"))])


# ---------------------------------------------------------------- Complaints
@router.post("/complaints")
def create_complaint(
    title: str = Form(...),
    description: str = Form(...),
    categoryId: str = Form(...),
    location: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("student", "staff", "admin")),
):
    if not db.get(Category, categoryId):
        raise HTTPException(400, "Invalid category")

    attachments = []
    if file and file.filename:
        name = f"{uid()}_{os.path.basename(file.filename)}"
        with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
            shutil.copyfileobj(file.file, f)
        attachments.append(f"/uploads/{name}")

    # Duplicate detection: title similarity against open complaints in same category
    dup_of = None
    open_same = db.scalars(select(Complaint).where(
        Complaint.category_id == categoryId, Complaint.status.in_(["open", "in_progress", "escalated"])))
    for c in open_same:
        if SequenceMatcher(None, c.title.lower(), title.lower()).ratio() > 0.85:
            dup_of = c.id
            break

    c = Complaint(title=title, description=description, category_id=categoryId, created_by=user.id,
                  location=location, attachments=attachments, is_duplicate_of=dup_of)
    db.add(c)
    db.flush()
    log(db, c.id, user.id, "created", None, "open")
    for admin in db.scalars(select(User).where(User.role == "admin")):
        notify(db, admin.id, c.id, "status_update", f"New complaint: {title}")
    db.commit()
    return ok(row(c))


@router.get("/complaints")
def list_complaints(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    categoryId: Optional[str] = None,
    assignedTo: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    q = select(Complaint).order_by(Complaint.created_at.desc())
    if user.role == "student":
        q = q.where(Complaint.created_by == user.id)
    elif user.role == "staff":
        ids = [a.complaint_id for a in db.scalars(select(Assignment).where(Assignment.assigned_to == user.id))]
        q = q.where(Complaint.id.in_(ids))
    if status:
        q = q.where(Complaint.status == status)
    if priority:
        q = q.where(Complaint.priority == priority)
    if categoryId:
        q = q.where(Complaint.category_id == categoryId)
    if assignedTo and user.role == "admin":
        ids = [a.complaint_id for a in db.scalars(select(Assignment).where(Assignment.assigned_to == assignedTo))]
        q = q.where(Complaint.id.in_(ids))
    items = db.scalars(q).all()
    total = len(items)
    items = items[(page - 1) * limit: page * limit]
    return ok({"items": [row(c) for c in items], "page": page, "limit": limit, "total": total})


@router.get("/complaints/public")
def public_complaints(db: Session = Depends(get_db)):
    q = select(Complaint).where(Complaint.is_public == True).order_by(Complaint.upvotes.desc()).limit(50)  # noqa: E712
    return ok([row(c, exclude=("created_by",)) for c in db.scalars(q)])


@router.get("/complaints/{cid}")
def get_complaint(cid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = db.get(Complaint, cid)
    if not c:
        raise HTTPException(404, "Not found")
    if user.role == "student" and c.created_by != user.id:
        raise HTTPException(403, "Forbidden")
    comments = db.scalars(select(Comment).where(Comment.complaint_id == cid).order_by(Comment.created_at))
    comments = [row(m) for m in comments if user.role != "student" or not m.is_internal]
    logs = [row(l) for l in db.scalars(
        select(ActivityLog).where(ActivityLog.complaint_id == cid).order_by(ActivityLog.timestamp))]
    assignment = db.scalar(select(Assignment).where(Assignment.complaint_id == cid)
                           .order_by(Assignment.assigned_at.desc()))
    return ok({**row(c), "comments": comments, "activity": logs,
               "assignment": row(assignment) if assignment else None})


@router.post("/complaints/{cid}/comments")
def add_comment(cid: str, req: CommentRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = db.get(Complaint, cid)
    if not c:
        raise HTTPException(404, "Not found")
    if user.role == "student" and c.created_by != user.id:
        raise HTTPException(403, "Forbidden")
    internal = req.isInternal and user.role != "student"
    m = Comment(complaint_id=cid, author_id=user.id, message=req.message, is_internal=internal)
    db.add(m)
    log(db, cid, user.id, "commented")
    if user.id != c.created_by and not internal:
        notify(db, c.created_by, cid, "comment", f"New comment on '{c.title}'")
    db.commit()
    return ok(row(m))


@router.post("/complaints/{cid}/upvote")
def upvote(cid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = db.get(Complaint, cid)
    if not c:
        raise HTTPException(404, "Not found")
    if db.scalar(select(Upvote).where(Upvote.complaint_id == cid, Upvote.user_id == user.id)):
        raise HTTPException(400, "Already upvoted")
    db.add(Upvote(complaint_id=cid, user_id=user.id))
    c.upvotes += 1
    db.commit()
    return ok({"upvotes": c.upvotes})


@router.post("/complaints/{cid}/assign")
def assign(cid: str, req: AssignRequest, db: Session = Depends(get_db),
           admin: User = Depends(require_roles("admin"))):
    c = db.get(Complaint, cid)
    staff_user = db.get(User, req.staffId)
    if not c or not staff_user or staff_user.role != "staff":
        raise HTTPException(400, "Invalid complaint or staff")
    due = now() + dt.timedelta(hours=req.dueHours) if req.dueHours else None
    a = Assignment(complaint_id=cid, assigned_to=staff_user.id, assigned_by=admin.id, due_at=due)
    db.add(a)
    if req.priority:
        log(db, cid, admin.id, "priority_changed", c.priority, req.priority)
        c.priority = req.priority
    old = c.status
    if c.status in ("open", "escalated"):
        c.status = "in_progress"
    log(db, cid, admin.id, "assigned", old, staff_user.name)
    notify(db, staff_user.id, cid, "assigned", f"You were assigned: {c.title}")
    notify(db, c.created_by, cid, "status_update", f"Your complaint '{c.title}' is now {c.status}")
    db.commit()
    return ok(row(a))


@router.patch("/complaints/{cid}/status")
def set_status(cid: str, req: StatusRequest, db: Session = Depends(get_db),
               user: User = Depends(require_roles("admin", "staff"))):
    c = db.get(Complaint, cid)
    if not c:
        raise HTTPException(404, "Not found")
    if user.role == "staff" and not db.scalar(
            select(Assignment).where(Assignment.complaint_id == cid, Assignment.assigned_to == user.id)):
        raise HTTPException(403, "Not assigned to you")
    old = c.status
    c.status = req.status
    if req.status == "resolved":
        c.resolved_at = now()
    log(db, cid, user.id, "resolved" if req.status == "resolved" else "status_changed", old, req.status)
    notify(db, c.created_by, cid, "status_update", f"Your complaint '{c.title}' is now {req.status}")
    db.commit()
    return ok(row(c))


# ---------------------------------------------------------------- Notifications
@router.get("/notifications")
def my_notifications(db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Notification).where(Notification.user_id == user.id).order_by(Notification.sent_at.desc()).limit(50)
    return ok([row(n) for n in db.scalars(q)])


@router.post("/notifications/{nid}/read")
def read_notification(nid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    n = db.get(Notification, nid)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Not found")
    n.is_read = True
    db.commit()
    return ok(row(n))


# ---------------------------------------------------------------- Analytics & admin
@router.get("/analytics/summary")
def analytics(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    complaints = db.scalars(select(Complaint)).all()
    cats = {c.id: c for c in db.scalars(select(Category))}
    depts = {d.id: d for d in db.scalars(select(Department))}

    by_status = Counter(c.status for c in complaints)
    by_cat = Counter(cats[c.category_id].name for c in complaints if c.category_id in cats)
    resolved = [c for c in complaints if c.resolved_at]
    avg = (sum((c.resolved_at - c.created_at).total_seconds() for c in resolved) / len(resolved) / 3600
           if resolved else 0)

    dept = defaultdict(lambda: {"resolved": 0, "pending": 0, "hours": [], "slaBreaches": 0})
    for c in complaints:
        cat = cats.get(c.category_id)
        if not cat:
            continue
        d = dept[cat.department_id]
        if c.resolved_at:
            d["resolved"] += 1
            hrs = (c.resolved_at - c.created_at).total_seconds() / 3600
            d["hours"].append(hrs)
            if hrs > cat.sla_hours:
                d["slaBreaches"] += 1
        else:
            d["pending"] += 1
            if c.escalation_level > 0:
                d["slaBreaches"] += 1

    trend = defaultdict(lambda: {"created": 0, "resolved": 0})
    for c in complaints:
        trend[c.created_at.strftime("%Y-%m-%d")]["created"] += 1
        if c.resolved_at:
            trend[c.resolved_at.strftime("%Y-%m-%d")]["resolved"] += 1

    return ok({
        "totalComplaints": len(complaints),
        "byStatus": {s: by_status.get(s, 0) for s in ["open", "in_progress", "resolved", "escalated", "closed"]},
        "byCategory": [{"category": k, "count": v} for k, v in by_cat.most_common()],
        "avgResolutionHours": round(avg, 2),
        "departmentPerformance": [
            {"departmentId": k, "name": depts[k].name if k in depts else "?", "resolved": v["resolved"],
             "pending": v["pending"],
             "avgResolutionHours": round(sum(v["hours"]) / len(v["hours"]), 2) if v["hours"] else 0,
             "slaBreaches": v["slaBreaches"]} for k, v in dept.items()],
        "trend": [{"date": k, **v} for k, v in sorted(trend.items())],
    })


@router.post("/admin/escalate/run")
def trigger_escalation(hours: Optional[float] = None, db: Session = Depends(get_db),
                       _: User = Depends(require_roles("admin"))):
    """Manually run escalation. Pass ?hours=0 to force-escalate everything (great for demos)."""
    return ok({"escalated": run_escalation(db, hours)})
