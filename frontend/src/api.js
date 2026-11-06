// One function for every call to the server (/api/...).
// - The session cookie is sent by the browser itself; JavaScript never sees it (HttpOnly).
// - Every POST carries the CSRF token in the X-CSRF-Token header (app/api.py, check_csrf).
// - A 401 answer means "not logged in": we go to the login page.

let csrfToken = null;

export async function me() {
  const data = await request("GET", "/me");
  csrfToken = data.csrf;
  return data;          // { user: {email, role} or null, csrf, coverage, examples }
}

export async function api(path, body) {
  const method = body === undefined ? "GET" : "POST";
  if (method === "POST" && !csrfToken) await me();
  return request(method, path, body);
}

async function request(method, path, body) {
  const headers = {};
  if (method === "POST") {
    headers["Content-Type"] = "application/json";
    headers["X-CSRF-Token"] = csrfToken;
  }
  const res = await fetch("/api" + path, {
    method, headers, credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && path !== "/login") {
    window.location.assign("/app/login");
  }
  if (!res.ok) {
    // FastAPI puts the message in "detail" (a text, or a list for a badly formed request)
    const detail = typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.";
    throw new Error(detail);
  }
  if (data.csrf) csrfToken = data.csrf;      // a new token after login
  return data;
}
