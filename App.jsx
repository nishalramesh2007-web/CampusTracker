import { useEffect, useState, useCallback } from "react";
import { api, auth, API } from "./api.js";

const Badge = ({ kind, value }) => <span className={`badge ${kind}-${value}`}>{value.replace("_", " ")}</span>;
const fmt = (d) => new Date(d + "Z").toLocaleString();

/* ---------------------------------------------------------------- Login */
function Login({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ name: "", email: "", password: "", rollNo: "" });
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setErr("");
    try {
      const data = await api(`/auth/${mode}`, { method: "POST", body: f });
      auth.set(data.token, data.user);
      onLogin(data.user);
    } catch (e) { setErr(e.message); }
  }

  return (
    <form className="card auth stack" onSubmit={submit}>
      <h2>{mode === "login" ? "Sign in" : "Create student account"}</h2>
      {mode === "register" && <>
        <input placeholder="Full name" value={f.name} onChange={set("name")} required />
        <input placeholder="Roll no (optional)" value={f.rollNo} onChange={set("rollNo")} />
      </>}
      <input type="email" placeholder="Email" value={f.email} onChange={set("email")} required />
      <input type="password" placeholder="Password" value={f.password} onChange={set("password")} required />
      {err && <div className="error">{err}</div>}
      <button>{mode === "login" ? "Sign in" : "Register"}</button>
      <button type="button" className="ghost" onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "New student? Register" : "Have an account? Sign in"}
      </button>
      <div className="muted">Demo: admin@campus.edu / admin123 · staff@campus.edu / staff123 · student@campus.edu / student123</div>
    </form>
  );
}

/* ---------------------------------------------------------------- New complaint */
function NewComplaint({ categories, onCreated }) {
  const [f, setF] = useState({ title: "", description: "", categoryId: "", location: "" });
  const [file, setFile] = useState(null);
  const [msg, setMsg] = useState("");

  async function submit(e) {
    e.preventDefault();
    const form = new FormData();
    Object.entries(f).forEach(([k, v]) => v && form.append(k, v));
    if (file) form.append("file", file);
    try {
      const c = await api("/complaints", { method: "POST", form });
      setMsg(c.is_duplicate_of ? "Submitted (flagged as possible duplicate)." : "Submitted!");
      setF({ title: "", description: "", categoryId: "", location: "" });
      setFile(null);
      onCreated();
    } catch (e) { setMsg(e.message); }
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>Raise a complaint</h2>
      <input placeholder="Title" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} required />
      <textarea placeholder="Describe the issue" value={f.description}
        onChange={(e) => setF({ ...f, description: e.target.value })} required />
      <div className="row">
        <select value={f.categoryId} onChange={(e) => setF({ ...f, categoryId: e.target.value })} required>
          <option value="">Category…</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input placeholder="Location (e.g. Block A, Lab 2)" value={f.location}
          onChange={(e) => setF({ ...f, location: e.target.value })} />
        <input type="file" accept="image/*" onChange={(e) => setFile(e.target.files[0])} />
      </div>
      <div className="row"><button>Submit</button><span className="muted">{msg}</span></div>
    </form>
  );
}

/* ---------------------------------------------------------------- Complaint detail */
function Detail({ id, user, staff, onChanged, onClose }) {
  const [c, setC] = useState(null);
  const [msg, setMsg] = useState("");
  const load = useCallback(() => api(`/complaints/${id}`).then(setC), [id]);
  useEffect(() => { load(); }, [load]);
  if (!c) return null;

  const run = async (fn) => { await fn(); await load(); onChanged(); };
  const canWork = user.role === "admin" || user.role === "staff";

  return (
    <div className="card stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>{c.title}</h2>
        <button className="ghost small" onClick={onClose}>Close</button>
      </div>
      <div className="row"><Badge kind="s" value={c.status} /><Badge kind="p" value={c.priority} />
        <span className="muted">{c.location} · {fmt(c.created_at)}</span></div>
      <p>{c.description}</p>
      {c.attachments.map((a) => <img key={a} src={API + a} alt="" style={{ maxWidth: 240, borderRadius: 6 }} />)}

      {canWork && (
        <div className="row">
          {user.role === "admin" && (
            <select defaultValue="" onChange={(e) => e.target.value && run(() =>
              api(`/complaints/${id}/assign`, { method: "POST", body: { staffId: e.target.value, priority: "high", dueHours: 24 } }))}>
              <option value="">Assign to staff…</option>
              {staff.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          )}
          {["in_progress", "resolved", "closed"].map((s) => (
            <button key={s} className="small ghost"
              onClick={() => run(() => api(`/complaints/${id}/status`, { method: "PATCH", body: { status: s } }))}>
              Mark {s.replace("_", " ")}
            </button>
          ))}
        </div>
      )}

      <h3>Comments</h3>
      {c.comments.map((m) => <div key={m.id} className="muted">• {m.message} {m.is_internal && "(internal)"}</div>)}
      <div className="row">
        <input style={{ flex: 1 }} placeholder="Add a comment" value={msg} onChange={(e) => setMsg(e.target.value)} />
        <button className="small" onClick={() => msg && run(async () => {
          await api(`/complaints/${id}/comments`, { method: "POST", body: { message: msg } }); setMsg("");
        })}>Send</button>
      </div>

      <h3>Timeline</h3>
      {c.activity.map((a) => (
        <div key={a.id} className="muted">{fmt(a.timestamp)} — {a.action}{a.to_value ? ` → ${a.to_value}` : ""}</div>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- Complaint table */
function ComplaintTable({ items, catName, onOpen }) {
  return (
    <table>
      <thead><tr><th>Title</th><th>Category</th><th>Status</th><th>Priority</th><th>Created</th><th></th></tr></thead>
      <tbody>
        {items.map((c) => (
          <tr key={c.id}>
            <td>{c.title}{c.is_duplicate_of && <span className="muted"> (dup?)</span>}</td>
            <td>{catName(c.category_id)}</td>
            <td><Badge kind="s" value={c.status} /></td>
            <td><Badge kind="p" value={c.priority} /></td>
            <td className="muted">{fmt(c.created_at)}</td>
            <td><button className="small" onClick={() => onOpen(c.id)}>Open</button></td>
          </tr>
        ))}
        {!items.length && <tr><td colSpan="6" className="muted">Nothing here yet.</td></tr>}
      </tbody>
    </table>
  );
}

/* ---------------------------------------------------------------- Analytics */
function Analytics({ data }) {
  if (!data) return null;
  const max = Math.max(1, ...data.byCategory.map((x) => x.count));
  return (
    <div className="card stack">
      <h2>Analytics</h2>
      <div className="grid">
        <div className="stat"><b>{data.totalComplaints}</b>Total</div>
        {Object.entries(data.byStatus).map(([k, v]) => <div className="stat" key={k}><b>{v}</b>{k.replace("_", " ")}</div>)}
        <div className="stat"><b>{data.avgResolutionHours}h</b>Avg resolution</div>
      </div>
      <h3>Most common issues</h3>
      {data.byCategory.map((x) => (
        <div key={x.category} className="row">
          <span style={{ width: 110 }}>{x.category}</span>
          <div className="bar" style={{ width: `${(x.count / max) * 60}%` }} /> <span>{x.count}</span>
        </div>
      ))}
      <h3>Department performance</h3>
      <table>
        <thead><tr><th>Dept</th><th>Resolved</th><th>Pending</th><th>Avg hrs</th><th>SLA breaches</th></tr></thead>
        <tbody>{data.departmentPerformance.map((d) => (
          <tr key={d.departmentId}><td>{d.name}</td><td>{d.resolved}</td><td>{d.pending}</td>
            <td>{d.avgResolutionHours}</td><td>{d.slaBreaches}</td></tr>))}</tbody>
      </table>
    </div>
  );
}

/* ---------------------------------------------------------------- Public board */
function PublicBoard({ items, catName, onUpvote }) {
  return (
    <div className="card">
      <h2>Public transparency board</h2>
      <table>
        <thead><tr><th>Issue</th><th>Category</th><th>Status</th><th>Votes</th><th></th></tr></thead>
        <tbody>{items.map((c) => (
          <tr key={c.id}><td>{c.title}</td><td>{catName(c.category_id)}</td>
            <td><Badge kind="s" value={c.status} /></td><td>{c.upvotes}</td>
            <td><button className="small ghost" onClick={() => onUpvote(c.id)}>▲ Upvote</button></td></tr>))}</tbody>
      </table>
    </div>
  );
}

/* ---------------------------------------------------------------- Dashboard */
function Dashboard({ user, onLogout }) {
  const [tab, setTab] = useState("complaints");
  const [cats, setCats] = useState([]);
  const [staff, setStaff] = useState([]);
  const [items, setItems] = useState([]);
  const [pub, setPub] = useState([]);
  const [stats, setStats] = useState(null);
  const [notifs, setNotifs] = useState([]);
  const [filter, setFilter] = useState("");
  const [openId, setOpenId] = useState(null);

  const catName = (id) => cats.find((c) => c.id === id)?.name || "-";

  const refresh = useCallback(async () => {
    const q = filter ? `?status=${filter}` : "";
    const [list, pb, n] = await Promise.all([api(`/complaints${q}`), api("/complaints/public"), api("/notifications")]);
    setItems(list.items); setPub(pb); setNotifs(n);
    if (user.role === "admin") setStats(await api("/analytics/summary"));
  }, [filter, user.role]);

  useEffect(() => {
    api("/meta/categories").then(setCats);
    if (user.role === "admin") api("/meta/staff").then(setStaff);
  }, [user.role]);
  useEffect(() => { refresh(); }, [refresh]);

  const unread = notifs.filter((n) => !n.is_read).length;
  const tabs = ["complaints", "public", "notifications", ...(user.role === "admin" ? ["analytics"] : [])];

  return (
    <>
      <header>
        <h1>🏫 Campus Complaint Tracker</h1>
        <div className="row">
          <span className="muted">{user.name} ({user.role})</span>
          <button className="ghost small" onClick={onLogout}>Logout</button>
        </div>
      </header>
      <main>
        <div className="tabs">
          {tabs.map((t) => (
            <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
              {t}{t === "notifications" && unread ? ` (${unread})` : ""}
            </button>))}
        </div>

        {tab === "complaints" && <>
          {user.role === "student" && <NewComplaint categories={cats} onCreated={refresh} />}
          {openId && <Detail id={openId} user={user} staff={staff} onChanged={refresh} onClose={() => setOpenId(null)} />}
          <div className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2>{user.role === "student" ? "My complaints" : "Complaints"}</h2>
              <select value={filter} onChange={(e) => setFilter(e.target.value)}>
                <option value="">All statuses</option>
                {["open", "in_progress", "escalated", "resolved", "closed"].map((s) => <option key={s}>{s}</option>)}
              </select>
              {user.role === "admin" && (
                <button className="small ghost" onClick={async () => {
                  const r = await api("/admin/escalate/run", { method: "POST" });
                  alert(`${r.escalated.length} complaint(s) escalated`); refresh();
                }}>Run escalation check</button>)}
            </div>
            <ComplaintTable items={items} catName={catName} onOpen={setOpenId} />
          </div>
        </>}

        {tab === "public" && <PublicBoard items={pub} catName={catName}
          onUpvote={async (id) => { try { await api(`/complaints/${id}/upvote`, { method: "POST" }); } catch (e) { alert(e.message); } refresh(); }} />}

        {tab === "notifications" && (
          <div className="card stack">
            <h2>Notifications</h2>
            {notifs.map((n) => (
              <div key={n.id} className="row" style={{ opacity: n.is_read ? 0.5 : 1 }}>
                <span>{n.message}</span><span className="muted">{fmt(n.sent_at)}</span>
                {!n.is_read && <button className="small ghost" onClick={async () => { await api(`/notifications/${n.id}/read`, { method: "POST" }); refresh(); }}>Mark read</button>}
              </div>))}
            {!notifs.length && <span className="muted">No notifications.</span>}
          </div>
        )}

        {tab === "analytics" && <Analytics data={stats} />}
      </main>
    </>
  );
}

export default function App() {
  const [user, setUser] = useState(auth.user);
  if (!user) return <Login onLogin={setUser} />;
  return <Dashboard user={user} onLogout={() => { auth.clear(); setUser(null); }} />;
}
