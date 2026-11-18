export const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const auth = {
  get token() { return localStorage.getItem("token"); },
  get user() { try { return JSON.parse(localStorage.getItem("user")); } catch { return null; } },
  set(token, user) { localStorage.setItem("token", token); localStorage.setItem("user", JSON.stringify(user)); },
  clear() { localStorage.removeItem("token"); localStorage.removeItem("user"); },
};

export async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;
  let payload;
  if (form) payload = form;
  else if (body) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  const res = await fetch(API + path, { method, headers, body: payload });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || "Request failed");
  return json.data;
}
