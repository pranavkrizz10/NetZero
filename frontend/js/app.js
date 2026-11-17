/* ============================================================
   NetZero front-end — a tiny hash-routed SPA, no build step.
   Views: auth, dashboard (your groups), group detail (the star:
   the simplified settle-up plan), plus expense entry (manual +
   natural language) and the category-correction feedback loop.
   ============================================================ */

const CATS = {
  "Food & Dining":    { c: "#E8590C", bg: "#FCE9DD", e: "🍽️" },
  "Groceries":        { c: "#2F9E44", bg: "#E3F3E7", e: "🛒" },
  "Transport":        { c: "#1971C2", bg: "#E1ECF7", e: "🚗" },
  "Rent & Utilities": { c: "#6741D9", bg: "#EBE6FA", e: "🏠" },
  "Entertainment":    { c: "#E64980", bg: "#FBE3ED", e: "🎬" },
  "Shopping":         { c: "#F08C00", bg: "#FDEECF", e: "🛍️" },
  "Travel":           { c: "#0CA678", bg: "#DBF3EC", e: "✈️" },
  "Health":           { c: "#E03131", bg: "#FADEDE", e: "💊" },
  "Other":            { c: "#868E96", bg: "#ECEDEF", e: "📌" },
};
const CAT_NAMES = Object.keys(CATS);

const app = document.getElementById("app");
const topbar = document.getElementById("topbar");
const whoami = document.getElementById("whoami");

let currentDetail = null;       // cached group detail for the open group
let addTab = "quick";           // which expense-entry tab is active

// ---------- helpers ----------
const fmt = (n) =>
  "₹" + Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function toast(msg, isErr = false) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = "toast" + (isErr ? " err" : "");
  t.hidden = false;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => (t.hidden = true), 3200);
}

function catChip(cat, source) {
  const m = CATS[cat] || CATS.Other;
  const flag = source === "model" ? ' <span class="model-flag">✨</span>' : "";
  return `<span class="cat-chip" style="background:${m.bg};color:${m.c}">${m.e} ${esc(cat)}${flag}</span>`;
}

function netClass(n) { return n > 0.004 ? "pos" : n < -0.004 ? "neg" : "zero"; }

// ============================================================
//  ROUTER
// ============================================================
window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("logout-btn").onclick = () => {
    API.clearAuth();
    location.hash = "#/login";
  };
  route();
});

function route() {
  const hash = location.hash || "#/";
  if (!API.token && hash !== "#/register") { renderAuth("login"); return; }
  if (hash === "#/login") { renderAuth("login"); return; }
  if (hash === "#/register") { renderAuth("register"); return; }

  topbar.hidden = false;
  whoami.textContent = API.user ? API.user.name : "";

  const gm = hash.match(/^#\/group\/(\d+)$/);
  if (gm) { renderGroup(Number(gm[1])); return; }
  renderDashboard();
}

// ============================================================
//  AUTH
// ============================================================
function renderAuth(mode) {
  topbar.hidden = true;
  const isLogin = mode === "login";
  app.innerHTML = `
    <div class="auth-wrap">
      <div class="auth-hero">
        <div class="brand-mark">Net<span class="brand-zero">0</span></div>
        <p>Split shared costs. Settle up in the fewest payments.</p>
      </div>
      <div class="card">
        <div class="card-title">${isLogin ? "Log in" : "Create your account"}</div>
        ${isLogin ? "" : `
          <div class="field"><label>Name</label><input type="text" id="a-name" placeholder="Your name"></div>`}
        <div class="field"><label>Email</label><input type="email" id="a-email" placeholder="you@example.com"></div>
        <div class="field"><label>Password</label><input type="password" id="a-pass" placeholder="••••••"></div>
        <button class="btn" id="a-submit" style="width:100%">${isLogin ? "Log in" : "Sign up"}</button>
        <div class="auth-toggle">
          ${isLogin
            ? `New here? <a href="#/register">Create an account</a>`
            : `Already have an account? <a href="#/login">Log in</a>`}
        </div>
      </div>
      ${isLogin ? `<p class="muted" style="text-align:center;font-size:13px">
        Demo login: <b>hari@demo.com</b> / <b>password</b></p>` : ""}
    </div>`;

  document.getElementById("a-submit").onclick = async () => {
    const email = document.getElementById("a-email").value.trim();
    const password = document.getElementById("a-pass").value;
    try {
      let res;
      if (isLogin) {
        res = await API.post("/api/auth/login", { email, password });
      } else {
        const name = document.getElementById("a-name").value.trim();
        res = await API.post("/api/auth/register", { name, email, password });
      }
      API.setAuth(res.token, res.user);
      location.hash = "#/";
    } catch (e) { toast(e.message, true); }
  };
  // enter-to-submit
  app.querySelectorAll("input").forEach((i) =>
    i.addEventListener("keydown", (ev) => { if (ev.key === "Enter") document.getElementById("a-submit").click(); }));
}

// ============================================================
//  DASHBOARD
// ============================================================
async function renderDashboard() {
  app.innerHTML = `<div class="center-load">Loading your groups…</div>`;
  let groups;
  try { groups = await API.get("/api/groups"); }
  catch (e) { toast(e.message, true); return; }

  const total = groups.reduce((s, g) => s + g.your_net, 0);
  const totalLabel = total > 0.004 ? "you are owed overall"
    : total < -0.004 ? "you owe overall" : "you're all square";

  app.innerHTML = `
    <div class="page-head">
      <h1>Your groups</h1>
      <div class="summary-net ${netClass(total)}">${fmt(Math.abs(total))} <span class="muted" style="font-family:var(--body);font-size:13px">${totalLabel}</span></div>
    </div>
    <div class="card">
      <div class="row" style="gap:10px">
        <input type="text" id="new-group" placeholder="New group name — e.g. Flat 3B, Goa Trip…" />
        <button class="btn" id="create-group">Create</button>
      </div>
    </div>
    ${groups.length === 0
      ? `<div class="empty">No groups yet. Create one above to start splitting expenses.</div>`
      : `<div class="group-grid">${groups.map(groupCard).join("")}</div>`}
  `;

  document.getElementById("create-group").onclick = createGroup;
  document.getElementById("new-group").addEventListener("keydown",
    (e) => { if (e.key === "Enter") createGroup(); });
  app.querySelectorAll(".group-card").forEach((c) =>
    (c.onclick = () => (location.hash = `#/group/${c.dataset.id}`)));
}

function groupCard(g) {
  const label = g.your_net > 0.004 ? "you are owed"
    : g.your_net < -0.004 ? "you owe" : "settled up";
  return `
    <div class="group-card" data-id="${g.id}">
      <h3>${esc(g.name)}</h3>
      <div class="meta">${g.member_count} member${g.member_count === 1 ? "" : "s"}</div>
      <div class="net ${netClass(g.your_net)}">
        ${g.your_net === 0 ? "✓ settled up" : fmt(Math.abs(g.your_net))}
        <span class="muted" style="font-weight:400;font-size:12px">${g.your_net === 0 ? "" : label}</span>
      </div>
    </div>`;
}

async function createGroup() {
  const input = document.getElementById("new-group");
  const name = input.value.trim();
  if (!name) return;
  try {
    const g = await API.post("/api/groups", { name });
    location.hash = `#/group/${g.id}`;
  } catch (e) { toast(e.message, true); }
}

// ============================================================
//  GROUP DETAIL  (the star: settle-up plan)
// ============================================================
async function renderGroup(gid) {
  app.innerHTML = `<div class="center-load">Loading group…</div>`;
  let d;
  try { d = await API.get(`/api/groups/${gid}`); }
  catch (e) { toast(e.message, true); location.hash = "#/"; return; }
  currentDetail = d;

  app.innerHTML = `
    <a class="back" href="#/">← All groups</a>
    <div class="page-head"><h1>${esc(d.name)}</h1></div>

    ${settleHero(d)}

    <div class="card">
      <div class="card-title">Balances</div>
      <div class="bal-list">${d.simplify.balances.map(balItem).join("")}</div>
    </div>

    <div class="card">
      <div class="between" style="margin-bottom:12px">
        <div class="card-title" style="margin:0">Members</div>
      </div>
      <div class="member-chips">
        ${d.members.map((m) => `<span class="chip">${esc(m.name)}</span>`).join("")}
        <input type="email" id="add-member-email" placeholder="add member by email" style="width:220px" />
        <button class="btn btn-sm" id="add-member-btn">Add</button>
      </div>
    </div>

    ${addExpenseCard(d)}

    <div class="card">
      <div class="card-title">Expenses</div>
      ${d.expenses.length === 0
        ? `<div class="muted" style="padding:8px 0">No expenses yet.</div>`
        : d.expenses.map(expenseRow).join("")}
    </div>

    ${d.settlements.length ? settlementsCard(d) : ""}
  `;

  wireGroup(d);
}

function settleHero(d) {
  const s = d.simplify;
  const settled = s.transfers.length === 0;
  if (settled) {
    return `<div class="card settle-hero">
      <div class="card-title">Settle up</div>
      <div class="all-settled"><div class="big">All settled up 🎉</div>
      <div class="settle-sub" style="margin:6px 0 0">No payments needed — everyone's square.</div></div>
    </div>`;
  }
  const saved = s.naive_count - s.optimized_count;
  const savedNote = saved > 0
    ? `Simplified from <span class="strike">${s.naive_count} individual debts</span> down to just this.`
    : `The minimum set of payments to clear every balance.`;
  return `
    <div class="card settle-hero">
      <div class="card-title">Settle up</div>
      <div class="settle-headline">${s.optimized_count} payment${s.optimized_count === 1 ? "" : "s"} to clear everything</div>
      <div class="settle-sub">${savedNote}</div>
      ${s.transfers.map((t, i) => `
        <div class="transfer">
          <div class="transfer-flow">
            <span>${esc(t.from_name)}</span>
            <span class="transfer-arrow">→</span>
            <span>${esc(t.to_name)}</span>
          </div>
          <div class="transfer-amt">
            <span class="amt">${fmt(t.amount)}</span>
            <button class="btn-record" data-from="${t.from_user}" data-to="${t.to_user}" data-amt="${t.amount}">Record</button>
          </div>
        </div>`).join("")}
    </div>`;
}

function balItem(b) {
  const label = b.net > 0.004 ? "is owed" : b.net < -0.004 ? "owes" : "settled";
  return `<div class="bal-item">
    <div class="bal-name">${esc(b.name)}</div>
    <div class="bal-amt ${netClass(b.net)}">${b.net === 0 ? "✓" : fmt(Math.abs(b.net))}</div>
    <div class="bal-label">${label}</div>
  </div>`;
}

function expenseRow(e) {
  const m = CATS[e.category] || CATS.Other;
  const shareText = e.shares.map((s) => `${esc(s.name)} ${fmt(s.share)}`).join(" · ");
  return `
    <div class="exp" data-id="${e.id}">
      <div class="exp-left">
        <div class="exp-cat-dot" style="background:${m.bg}">${m.e}</div>
        <div style="min-width:0">
          <div class="exp-desc">${esc(e.description)}</div>
          <div class="exp-meta">${esc(e.paid_by_name)} paid · split: ${esc(shareText)}</div>
          <div>${catChip(e.category, e.category_source)}
            <button class="link-btn recat-btn" data-id="${e.id}" data-cat="${esc(e.category)}">fix</button>
          </div>
        </div>
      </div>
      <div class="exp-right">
        <div class="exp-amt">${fmt(e.amount)}</div>
        <button class="link-btn del-btn" data-id="${e.id}">delete</button>
      </div>
    </div>`;
}

function settlementsCard(d) {
  return `<div class="card">
    <div class="card-title">Payment history</div>
    ${d.settlements.map((s) => `
      <div class="settle-row">
        <span>${esc(s.from_name)} → ${esc(s.to_name)}</span>
        <span class="money">${fmt(s.amount)}</span>
      </div>`).join("")}
  </div>`;
}

// ---------- add-expense card (tabs: quick / manual) ----------
function addExpenseCard(d) {
  return `
    <div class="card">
      <div class="card-title">Add an expense</div>
      <div class="tabs">
        <button class="tab ${addTab === "quick" ? "active" : ""}" data-tab="quick">✨ Quick add (type it)</button>
        <button class="tab ${addTab === "manual" ? "active" : ""}" data-tab="manual">Manual</button>
      </div>
      <div id="quick-pane" ${addTab === "quick" ? "" : "hidden"}>
        <div class="field">
          <input type="text" id="nlp-text" placeholder="e.g. I paid 1200 for dinner with Raj and Priya, split equally" />
        </div>
        <button class="btn" id="nlp-parse">Parse it →</button>
        <div class="nlp-examples">
          Try: <code>₹450 auto to airport</code> · <code>Raj paid 2k for hotel split with everyone</code> · <code>600 swiggy with Priya</code>
        </div>
      </div>
      <div id="manual-pane" ${addTab === "manual" ? "" : "hidden"}>
        ${manualForm(d)}
      </div>
    </div>`;
}

function manualForm(d) {
  const me = API.user.id;
  const catOptions = `<option value="">✨ Auto-detect</option>` +
    CAT_NAMES.map((c) => `<option value="${esc(c)}">${c}</option>`).join("");
  return `
    <div id="nlp-warnings"></div>
    <div class="field"><label>Description</label>
      <input type="text" id="m-desc" placeholder="What was it for?" /></div>
    <div class="row wrap">
      <div class="field" style="flex:1;min-width:130px"><label>Amount (₹)</label>
        <input type="number" id="m-amount" min="0" step="0.01" placeholder="0.00" /></div>
      <div class="field" style="flex:1;min-width:130px"><label>Paid by</label>
        <select id="m-paidby">${d.members.map((m) =>
          `<option value="${m.id}" ${m.id === me ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select></div>
    </div>
    <div class="row wrap">
      <div class="field" style="flex:1;min-width:130px"><label>Split</label>
        <select id="m-split">
          <option value="equal">Equally</option>
          <option value="exact">Exact amounts</option>
          <option value="percent">Percentages</option>
        </select></div>
      <div class="field" style="flex:1;min-width:130px"><label>Category</label>
        <select id="m-category">${catOptions}</select>
        <div id="cat-hint" class="muted" style="font-size:12px;margin-top:4px"></div>
      </div>
    </div>
    <div class="field"><label>Split between</label>
      <div class="part-list" id="m-parts">
        ${d.members.map((m) => `
          <div class="part-row">
            <input type="checkbox" class="part-check" value="${m.id}" checked />
            <span class="part-name">${esc(m.name)}</span>
            <input type="number" class="part-value" data-uid="${m.id}" placeholder="" hidden />
          </div>`).join("")}
      </div>
    </div>
    <button class="btn" id="m-submit">Add expense</button>`;
}

// ============================================================
//  GROUP INTERACTIONS
// ============================================================
function wireGroup(d) {
  // add member
  document.getElementById("add-member-btn").onclick = async () => {
    const email = document.getElementById("add-member-email").value.trim();
    if (!email) return;
    try {
      await API.post(`/api/groups/${d.id}/members`, { email });
      toast("Member added.");
      renderGroup(d.id);
    } catch (e) { toast(e.message, true); }
  };

  // record settlement
  app.querySelectorAll(".btn-record").forEach((b) => {
    b.onclick = async () => {
      try {
        await API.post(`/api/groups/${d.id}/settle`, {
          from_user: Number(b.dataset.from),
          to_user: Number(b.dataset.to),
          amount: Number(b.dataset.amt),
        });
        toast("Payment recorded.");
        renderGroup(d.id);
      } catch (e) { toast(e.message, true); }
    };
  });

  // delete expense
  app.querySelectorAll(".del-btn").forEach((b) => {
    b.onclick = async () => {
      try { await API.del(`/api/expenses/${b.dataset.id}`); toast("Expense deleted."); renderGroup(d.id); }
      catch (e) { toast(e.message, true); }
    };
  });

  // fix category (feedback loop)
  app.querySelectorAll(".recat-btn").forEach((b) => {
    b.onclick = () => openCategoryPicker(b.dataset.id, b.dataset.cat, d.id);
  });

  // tabs
  app.querySelectorAll(".tab").forEach((t) => {
    t.onclick = () => {
      addTab = t.dataset.tab;
      document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
      document.getElementById("quick-pane").hidden = addTab !== "quick";
      document.getElementById("manual-pane").hidden = addTab !== "manual";
    };
  });

  // NLP parse
  const nlpBtn = document.getElementById("nlp-parse");
  if (nlpBtn) nlpBtn.onclick = () => parseNLP(d);
  const nlpInput = document.getElementById("nlp-text");
  if (nlpInput) nlpInput.addEventListener("keydown", (e) => { if (e.key === "Enter") parseNLP(d); });

  wireManualForm(d);
}

function wireManualForm(d) {
  const split = document.getElementById("m-split");
  const desc = document.getElementById("m-desc");
  const cat = document.getElementById("m-category");
  const catHint = document.getElementById("cat-hint");

  // toggle per-participant value inputs when split type changes
  const refreshValues = () => {
    const showValues = split.value !== "equal";
    app.querySelectorAll(".part-row").forEach((row) => {
      const check = row.querySelector(".part-check");
      const val = row.querySelector(".part-value");
      val.hidden = !(showValues && check.checked);
      val.placeholder = split.value === "percent" ? "%" : "₹";
    });
  };
  split.onchange = refreshValues;
  app.querySelectorAll(".part-check").forEach((c) => (c.onchange = refreshValues));

  // live category prediction on blur (shows the ML working)
  cat.dataset.touched = "false";
  cat.onchange = () => (cat.dataset.touched = "true");
  desc.addEventListener("blur", async () => {
    if (!desc.value.trim() || cat.dataset.touched === "true") return;
    try {
      const r = await API.post("/api/ml/categorize", { description: desc.value.trim() });
      cat.value = r.category;
      catHint.textContent = `✨ predicted (${Math.round(r.confidence * 100)}% sure) — change if wrong`;
    } catch (e) {}
  });

  document.getElementById("m-submit").onclick = () => submitExpense(d);
}

async function parseNLP(d) {
  const text = document.getElementById("nlp-text").value.trim();
  if (!text) return;
  const btn = document.getElementById("nlp-parse");
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>`;
  try {
    const draft = await API.post(`/api/groups/${d.id}/nlp-parse`, { text });
    // switch to manual tab, prefilled with the parsed draft for confirmation
    addTab = "manual";
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === "manual"));
    document.getElementById("quick-pane").hidden = true;
    document.getElementById("manual-pane").hidden = false;

    if (draft.description) document.getElementById("m-desc").value = draft.description;
    if (draft.amount != null) document.getElementById("m-amount").value = draft.amount;
    if (draft.paid_by != null) document.getElementById("m-paidby").value = draft.paid_by;
    document.getElementById("m-split").value = "equal";
    const cat = document.getElementById("m-category");
    if (draft.category) { cat.value = draft.category; cat.dataset.touched = "false"; }
    document.getElementById("cat-hint").textContent = draft.category ? `✨ predicted from your text` : "";

    // set participant checkboxes to the parsed set
    const ids = new Set(draft.participant_ids || []);
    app.querySelectorAll(".part-check").forEach((c) => (c.checked = ids.has(Number(c.value))));

    const warnBox = document.getElementById("nlp-warnings");
    warnBox.innerHTML = (draft.warnings || []).map((w) => `<div class="warn">⚠ ${esc(w)}</div>`).join("");
    toast("Parsed — review and confirm below.");
  } catch (e) { toast(e.message, true); }
  finally { btn.disabled = false; btn.textContent = "Parse it →"; }
}

async function submitExpense(d) {
  const description = document.getElementById("m-desc").value.trim();
  const amount = Number(document.getElementById("m-amount").value);
  const paid_by = Number(document.getElementById("m-paidby").value);
  const split_type = document.getElementById("m-split").value;
  const catSel = document.getElementById("m-category");

  if (!description) return toast("Add a description.", true);
  if (!(amount > 0)) return toast("Enter an amount greater than zero.", true);

  const participants = [];
  app.querySelectorAll(".part-row").forEach((row) => {
    const check = row.querySelector(".part-check");
    if (!check.checked) return;
    const uid = Number(check.value);
    if (split_type === "equal") { participants.push({ user_id: uid }); }
    else {
      const v = Number(row.querySelector(".part-value").value);
      participants.push({ user_id: uid, value: v });
    }
  });
  if (participants.length === 0) return toast("Pick at least one person to split with.", true);

  const body = { description, amount, paid_by, split_type, participants };
  // send category only if the user explicitly chose one; else let the model predict
  if (catSel.value && catSel.dataset.touched === "true") body.category = catSel.value;

  const btn = document.getElementById("m-submit");
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>`;
  try {
    await API.post(`/api/groups/${d.id}/expenses`, body);
    toast("Expense added.");
    renderGroup(d.id);
  } catch (e) { toast(e.message, true); btn.disabled = false; btn.textContent = "Add expense"; }
}

// simple inline category picker for corrections
function openCategoryPicker(expenseId, current, gid) {
  const choice = window.prompt(
    `Fix category. This correction trains the model.\n\nOptions:\n${CAT_NAMES.join(", ")}\n\nCurrent: ${current}`,
    current
  );
  if (!choice) return;
  const match = CAT_NAMES.find((c) => c.toLowerCase() === choice.trim().toLowerCase());
  if (!match) { toast("Not a valid category.", true); return; }
  API.put(`/api/expenses/${expenseId}/category`, { category: match })
    .then(() => { toast("Category fixed — the model will learn from this."); renderGroup(gid); })
    .catch((e) => toast(e.message, true));
}
