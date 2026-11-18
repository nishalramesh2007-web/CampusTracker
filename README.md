# Smart Campus Complaint & Issue Tracker

FastAPI + SQLite backend, React (Vite) frontend.

## Run

**Backend** (http://localhost:8000, docs at /docs)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend** (http://localhost:5173)
```bash
cd frontend
npm install
npm run dev
```

## Demo logins (seeded on first run)
| Role    | Email               | Password   |
|---------|---------------------|------------|
| Admin   | admin@campus.edu    | admin123   |
| Staff   | staff@campus.edu    | staff123   |
| Student | student@campus.edu  | student123 |

## Features
- Role-based auth (JWT): student / staff / admin
- Complaints with category, location, photo upload, status + priority
- Admin assigns to staff; status flow Open → In Progress → Resolved
- Auto-escalation: background job every 60s (`ESCALATION_INTERVAL_SEC`); threshold = category SLA × priority factor.
  Demo it instantly: Admin → "Run escalation check", or `POST /admin/escalate/run?hours=0`
- Comments (with internal notes), activity timeline, in-app notifications (+ email stub printed to console)
- Duplicate detection (title similarity), upvotes, public transparency board
- Analytics: status counts, common issues, avg resolution time, department performance, SLA breaches

## Layout
```
backend/app/  main.py (app, seed, escalation loop) · models.py · schemas.py · auth.py · routers.py · services.py
frontend/src/ App.jsx · api.js · styles.css
```

## Env vars
`JWT_SECRET` (set this in production), `ESCALATION_INTERVAL_SEC`, frontend `VITE_API_URL`.

## Deploy
Backend → Render (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`); frontend → Vercel with `VITE_API_URL` set.
Switch SQLite to PostgreSQL by changing the URL in `backend/app/database.py`.
