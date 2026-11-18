import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .auth import hash_password
from .database import Base, SessionLocal, engine
from .models import Category, Department, User
from .routers import UPLOAD_DIR, router
from .services import run_escalation

ESCALATION_INTERVAL_SEC = int(os.getenv("ESCALATION_INTERVAL_SEC", "60"))


def seed():
    db = SessionLocal()
    try:
        if db.scalar(select(Department)):
            return
        depts = {n: Department(name=n, email=f"{n.lower()}@campus.edu")
                 for n in ["IT", "Hostel", "Maintenance", "Academics"]}
        db.add_all(depts.values())
        db.flush()
        db.add_all([
            Category(name="WiFi", department_id=depts["IT"].id, sla_hours=24),
            Category(name="Hostel", department_id=depts["Hostel"].id, sla_hours=48),
            Category(name="Lab", department_id=depts["Academics"].id, sla_hours=72),
            Category(name="Maintenance", department_id=depts["Maintenance"].id, sla_hours=48),
            Category(name="Other", department_id=depts["Academics"].id, sla_hours=96),
        ])
        db.add_all([
            User(name="Admin", email="admin@campus.edu", password_hash=hash_password("admin123"), role="admin"),
            User(name="Staff One", email="staff@campus.edu", password_hash=hash_password("staff123"),
                 role="staff", department_id=depts["IT"].id),
            User(name="Student One", email="student@campus.edu", password_hash=hash_password("student123"),
                 role="student", roll_no="21CS001"),
        ])
        db.commit()
    finally:
        db.close()


async def escalation_loop():
    while True:
        await asyncio.sleep(ESCALATION_INTERVAL_SEC)
        db = SessionLocal()
        try:
            run_escalation(db)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    seed()
    task = asyncio.create_task(escalation_loop())
    yield
    task.cancel()


app = FastAPI(title="Smart Campus Complaint Tracker", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.include_router(router)
