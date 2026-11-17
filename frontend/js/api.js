/* Thin API client. Token persists in localStorage so login survives reloads
   (this is a real app served from a local server, not a sandboxed artifact). */
const API = {
  base: "",
  token: localStorage.getItem("nz_token") || null,
  user: JSON.parse(localStorage.getItem("nz_user") || "null"),

  setAuth(token, user) {
    this.token = token;
    this.user = user;
    localStorage.setItem("nz_token", token);
    localStorage.setItem("nz_user", JSON.stringify(user));
  },
  clearAuth() {
    this.token = null;
    this.user = null;
    localStorage.removeItem("nz_token");
    localStorage.removeItem("nz_user");
  },

  async req(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers["Authorization"] = "Bearer " + this.token;
    const res = await fetch(this.base + path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (res.status === 401) {
      // token expired / invalid -> bounce to login
      this.clearAuth();
      location.hash = "#/login";
    }
    if (!res.ok) {
      let msg = "Something went wrong.";
      try {
        const j = await res.json();
        msg = j.detail || msg;
      } catch (e) {}
      throw new Error(msg);
    }
    if (res.status === 204) return null;
    return res.json();
  },

  get(p) { return this.req("GET", p); },
  post(p, b) { return this.req("POST", p, b); },
  put(p, b) { return this.req("PUT", p, b); },
  del(p) { return this.req("DELETE", p); },
};
