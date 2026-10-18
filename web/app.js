"use strict";

const $ = (s) => document.querySelector(s);
const state = { source: "", fileLabel: "" };

const EXAMPLES = [
  "Summarize this document",
  "List all employees from Mumbai",
  "Find expenses above 5000",
  "Show students with GPA above 8",
  "Give me the top 5 highest expenses",
  "How many products are out of stock",
  "Find all rows related to laptops",
];

/* ---------- boot: load samples + chips ---------- */
async function boot() {
  $("#chips").innerHTML = EXAMPLES.map((q) => `<span class="chip">${q}</span>`).join("");
  $("#chips").querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () => { $("#queryInput").value = c.textContent; $("#queryInput").focus(); }));
  try {
    const r = await fetch("/api/samples");
    const { samples } = await r.json();
    const sel = $("#sampleSel");
    samples.forEach((s) => {
      const o = document.createElement("option");
      o.value = `sample:${s.name}`; o.textContent = `${s.name}  (${s.type})`;
      sel.appendChild(o);
    });
  } catch { /* ignore */ }
}

$("#sampleSel").addEventListener("change", (e) => {
  if (e.target.value) {
    state.source = e.target.value;
    state.fileLabel = e.target.value.split(":")[1];
    showActive(`Using sample <b>${state.fileLabel}</b>`);
    $("#fileInput").value = "";
  }
});

/* ---------- upload (click + drag) ---------- */
const drop = $("#drop");
$("#fileInput").addEventListener("change", (e) => { if (e.target.files[0]) uploadFile(e.target.files[0]); });
["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) uploadFile(f); });

async function uploadFile(file) {
  $("#dropText").textContent = `Uploading ${file.name}…`;
  const fd = new FormData(); fd.append("file", file);
  try {
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    const b = await r.json();
    if (!r.ok) { toast(b.error || "Upload failed"); resetDrop(); return; }
    state.source = `upload:${b.token}`; state.fileLabel = b.name;
    $("#sampleSel").value = "";
    $("#dropText").innerHTML = `<b style="color:var(--coral)">${b.name}</b> ready`;
    showActive(`Using uploaded file <b>${b.name}</b>`);
  } catch { toast("Upload failed"); resetDrop(); }
}
function resetDrop() { $("#dropText").innerHTML = "Drop a file or <u>browse</u> — PDF, Excel, CSV"; }
function showActive(html) { const el = $("#activeFile"); el.innerHTML = html; el.classList.remove("hidden"); }

/* ---------- ask ---------- */
$("#askBtn").addEventListener("click", ask);
$("#queryInput").addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });

function showState(which) {
  $("#loading").classList.toggle("hidden", which !== "loading");
  $("#error").classList.toggle("hidden", which !== "error");
  $("#result").classList.toggle("hidden", which !== "result");
}

async function ask() {
  const query = $("#queryInput").value.trim();
  if (!state.source) { toast("Choose a sample or upload a file first"); return; }
  if (!query) { toast("Type a question first"); return; }
  showState("loading");
  try {
    const r = await fetch("/api/query", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: state.source, query }),
    });
    const b = await r.json();
    if (!r.ok) { $("#errorMsg").textContent = b.error || "Something went wrong."; showState("error"); return; }
    render(b);
  } catch { $("#errorMsg").textContent = "Could not reach the server."; showState("error"); }
}

function render(d) {
  showState("result");
  $("#rFile").textContent = d.file_type;
  $("#rIntent").textContent = d.intent;
  $("#rConf").textContent = d.confidence;
  $("#rOrig").textContent = d.original_query;
  // highlight the words that changed during correction
  $("#rCorr").innerHTML = d.corrected ? diffHighlight(d.original_query, d.corrected_query) : escapeHtml(d.corrected_query);

  // result text — enlarge a single-number answer (aggregation)
  const m = d.result.match(/^(.*?=\s*)([\d.,]+)$/);
  $("#rText").innerHTML = m
    ? `${escapeHtml(m[1])}<span class="big">${escapeHtml(m[2])}</span>`
    : escapeHtml(d.result);

  const term = (d.meta && (d.meta.term || d.meta.value)) ? String(d.meta.term || d.meta.value).toLowerCase() : "";
  renderTable(d.table, term);
  $("#result").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderTable(table, term) {
  const wrap = $("#rTableWrap");
  if (!table) { wrap.classList.add("hidden"); return; }
  wrap.classList.remove("hidden");
  $("#rTable thead").innerHTML = "<tr>" + table.columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("") + "</tr>";
  $("#rTable tbody").innerHTML = table.rows.map((row) =>
    "<tr>" + table.columns.map((c) => {
      const v = row[c] == null ? "" : String(row[c]);
      const hit = term && v.toLowerCase().includes(term) ? " class=\"hit\"" : "";
      return `<td${hit}>${escapeHtml(v)}</td>`;
    }).join("") + "</tr>").join("");
}

/* ---------- helpers ---------- */
function diffHighlight(orig, corr) {
  const o = orig.toLowerCase().split(/\s+/);
  return corr.split(/\s+/).map((w, i) =>
    (o[i] && o[i] === w.toLowerCase()) ? escapeHtml(w) : `<mark>${escapeHtml(w)}</mark>`).join(" ");
}
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
let toastTimer;
function toast(msg) {
  const el = $("#toast"); el.textContent = msg; el.classList.remove("hidden");
  requestAnimationFrame(() => el.classList.add("show"));
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.classList.remove("show"); setTimeout(() => el.classList.add("hidden"), 300); }, 2600);
}

boot();
