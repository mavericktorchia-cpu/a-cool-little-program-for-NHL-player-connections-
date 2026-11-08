/* Shared by every page: roster data, name search, the teammate graph, daily puzzles,
   saved progress, the player picker, and the page links. Loaded after data.js. */
"use strict";

const SITE_ROOT = "https://mavericktorchia-cpu.github.io/a-cool-little-program-for-NHL-player-connections-/";
const DATA = window.NHL_DATA;

/* ---------- roster data ---------- */
// DATA.p = [[id, name, pos, birthYear], ...]
// DATA.r = {"TEAM-SEASON": [playerIndex, ...]}
// DATA.t = {TRI: "Full team name"}
const P = DATA.p.map(([id, name, pos, born]) => ({ id, name, pos, born, stints: [] }));
const byId = new Map(P.map((p, i) => [p.id, i]));
// Team-seasons in chronological order; a player's stints are indexes into this list.
const keys = Object.keys(DATA.r).sort((x, y) => x.split("-")[1] - y.split("-")[1] || (x < y ? -1 : 1));
const R = keys.map(k => DATA.r[k]);
keys.forEach((k, s) => R[s].forEach(i => P[i].stints.push(s)));

const norm = s => s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
P.forEach(p => { p.key = norm(p.name); p.words = p.key.split(" "); });

const team = s => keys[s].split("-")[0];
const season = s => keys[s].split("-")[1];
const seasonLabel = y => `${String(y).slice(0, 4)}–${String(y).slice(6)}`;
const stintLabel = s => `${team(s)} ${seasonLabel(season(s))}`;
const teamName = t => (DATA.t && DATA.t[t]) || t;
const posName = { C: "C", L: "LW", R: "RW", D: "D", G: "G" };
const posLong = { C: "Center", L: "Left wing", R: "Right wing", D: "Defenseman", G: "Goalie" };

function career(p) {
  if (!p.stints.length) return "no roster data";
  const first = season(p.stints[0]).slice(0, 4);
  const last = season(p.stints[p.stints.length - 1]).slice(4);
  return `${first}–${last} · ${[...new Set(p.stints.map(team))].join("/")}`;
}
const describe = p => `${posName[p.pos] || p.pos || "?"} · ${career(p)}`;
const seasonsOf = i => new Set(P[i].stints.map(season)).size;
const shared = (a, b) => { const mine = new Set(P[a].stints); return P[b].stints.filter(s => mine.has(s)); };

/* ---------- name search ---------- */
// Every typed word must start a word of the name. Exact names first, then longer careers.
function search(q, limit = 8) {
  const words = norm(q).split(" ").filter(Boolean);
  if (!words.length) return [];
  const whole = words.join(" "), lastWord = words[words.length - 1];
  const hits = [];
  for (let i = 0; i < P.length; i++) {
    const p = P[i];
    if (words.every(w => p.words.some(pw => pw.startsWith(w)))) {
      const exact = p.key === whole ? 1000 : 0;
      const lastHit = p.words[p.words.length - 1].startsWith(lastWord) ? 50 : 0;
      hits.push([exact + lastHit + p.stints.length, i]);
    }
  }
  return hits.sort((x, y) => y[0] - x[0]).slice(0, limit).map(h => h[1]);
}

/* ---------- teammate graph ---------- */
// Bidirectional breadth-first search: fewest teammate hops from a to b, skipping `avoid`.
function shortestPath(a, b, avoid = new Set()) {
  if (a === b) return [a];
  const fw = new Map([[a, -1]]), bw = new Map([[b, -1]]);
  const seenF = new Set(), seenB = new Set();
  let front = [a], back = [b];
  const expand = (frontier, tree, seen) => {
    const next = [];
    for (const p of frontier) for (const s of P[p].stints) {
      if (seen.has(s)) continue;
      seen.add(s);
      for (const o of R[s]) if (!tree.has(o) && !avoid.has(o)) { tree.set(o, p); next.push(o); }
    }
    return next;
  };
  while (front.length && back.length) {
    let meet;
    if (front.length <= back.length) { front = expand(front, fw, seenF); meet = front.find(p => bw.has(p)); }
    else { back = expand(back, bw, seenB); meet = back.find(p => fw.has(p)); }
    if (meet !== undefined) {
      const chain = [meet];
      for (let n = fw.get(meet); n !== -1; n = fw.get(n)) chain.unshift(n);
      for (let n = bw.get(meet); n !== -1; n = bw.get(n)) chain.push(n);
      return chain;
    }
  }
  return null;
}

/* ---------- daily puzzles ---------- */
// Pools for daily puzzles only count seasons before 2024-25, so weekly roster updates
// never change a day's puzzle.
const CUTOFF = 20242025;
const seasonsBefore = P.map(p => new Set(p.stints.map(season).filter(y => +y < CUTOFF)).size);
const poolOf = min => P.map((p, i) => i).filter(i => seasonsBefore[i] >= min);

function mulberry32(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const today = new Date();
const dayKey = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const dateKey = dayKey(today);
const dateSeed = +dateKey.replace(/-/g, "");
const todayLabel = today.toLocaleDateString(undefined, { month: "long", day: "numeric" });
// Puzzle number for a game whose #1 was on firstDay (Date.UTC).
const puzzleNumber = firstDay => Math.floor((Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()) - firstDay) / 86400000) + 1;

/* ---------- saved progress (this browser only) ---------- */
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
};
// Days in a row, ending today (or yesterday if today isn't done yet), where solved(entry) is true.
function streakFrom(hist, solved) {
  let n = 0;
  const d = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  if (!(hist[dayKey(d)] && solved(hist[dayKey(d)]))) d.setDate(d.getDate() - 1);
  while (hist[dayKey(d)] && solved(hist[dayKey(d)])) { n++; d.setDate(d.getDate() - 1); }
  return n;
}
// Whether today's daily puzzle of each game is finished.
const DAILY_DONE = {
  chain: () => !!(store.get("chain-daily-" + dateKey) || {}).done,
  mystery: () => !!(store.get("mystery-daily-" + dateKey) || {}).done,
  longer: () => ((store.get("longer-daily-" + dateKey) || {}).answers || []).length >= 10,
  roster: () => !!(store.get("roster-daily-" + dateKey) || {}).ended,
};
// One line about today's puzzle for each game, for the "Today's puzzles" cards.
// state: "todo" | "playing" | "done"
function dailySummary(game) {
  const today_ = store.get(`${game}-daily-${dateKey}`);
  if (game === "chain") {
    const hist = store.get("chain-history") || {};
    const streak = streakFrom(hist, h => h.links !== null);
    if (!today_) return { state: "todo", text: "Not played yet", streak };
    if (!today_.done) return { state: "playing", text: `In progress: ${plural(today_.chain.length - 1, "link", "links")} so far`, streak };
    const h = hist[dateKey] || {};
    return { state: "done", text: today_.gaveUp ? "Gave up" : `${plural(today_.chain.length - 1, "link", "links")} (par ${h.par ?? "?"})`, streak };
  }
  if (game === "mystery") {
    const streak = streakFrom(store.get("mystery-history") || {}, h => h.clues !== null);
    if (!today_) return { state: "todo", text: "Not played yet", streak };
    if (!today_.done) return { state: "playing", text: `In progress: clue ${today_.shown} of 7`, streak };
    return { state: "done", text: today_.won ? `Solved with ${today_.shown} of 7 clues` : "Stumped", streak };
  }
  if (game === "longer") {
    const answers = (today_ || {}).answers || [];
    const right = answers.filter(Boolean).length;
    const streak = streakFrom(store.get("longer-history") || {}, () => true);
    if (!answers.length) return { state: "todo", text: "Not played yet", streak };
    if (answers.length < 10) return { state: "playing", text: `In progress: round ${answers.length + 1} of 10`, streak };
    return { state: "done", text: `${right}/10 correct`, streak };
  }
  if (game === "roster") {
    const streak = streakFrom(store.get("roster-history") || {}, () => true);
    if (!today_ || !today_.startedAt) return { state: "todo", text: "Not played yet", streak };
    if (!today_.ended) return { state: "playing", text: `In progress: ${plural((today_.found || []).length, "player", "players")} named`, streak };
    const h = (store.get("roster-history") || {})[dateKey] || {};
    return { state: "done", text: `${h.found ?? (today_.found || []).length}/${h.total ?? "?"} named`, streak };
  }
  return { state: "todo", text: "" };
}

// A bar chart of every daily result saved in this browser, with today's bar highlighted.
function historyChart(game) {
  const hist = store.get(game + "-history") || {};
  const days = Object.keys(hist);
  // Each game sorts a day's result into one of its buckets.
  const BUCKETS = {
    chain: [["Par", h => h.links === h.par], ["+1", h => h.links === h.par + 1], ["+2", h => h.links === h.par + 2],
            ["+3 or more", h => h.links !== null && h.links >= h.par + 3], ["Gave up", h => h.links === null]],
    mystery: [1, 2, 3, 4, 5, 6, 7].map(n => [`${n} ${n === 1 ? "clue" : "clues"}`, h => h.clues === n]).concat([["Stumped", h => h.clues === null]]),
    longer: [["10/10", h => h.right === 10], ["8–9", h => h.right >= 8 && h.right < 10], ["6–7", h => h.right >= 6 && h.right < 8],
             ["4–5", h => h.right >= 4 && h.right < 6], ["0–3", h => h.right < 4]],
    roster: [["80%+", h => h.found / h.total >= .8], ["60–79%", h => h.found / h.total >= .6 && h.found / h.total < .8],
             ["40–59%", h => h.found / h.total >= .4 && h.found / h.total < .6], ["20–39%", h => h.found / h.total >= .2 && h.found / h.total < .4],
             ["Under 20%", h => h.found / h.total < .2]],
  }[game];
  const box = document.createElement("div");
  box.className = "dist";
  if (!BUCKETS || !days.length) return box;
  const counts = BUCKETS.map(([, test]) => days.filter(d => test(hist[d])).length);
  const max = Math.max(1, ...counts);
  const todayIdx = hist[dateKey] ? BUCKETS.findIndex(([, test]) => test(hist[dateKey])) : -1;
  const h = document.createElement("h3");
  h.textContent = `Your results · ${plural(days.length, "day", "days")} played`;
  box.appendChild(h);
  BUCKETS.forEach(([label], k) => {
    const row = document.createElement("div");
    row.className = "dist-row" + (k === todayIdx ? " today" : "");
    const l = document.createElement("span"); l.className = "dist-label"; l.textContent = label;
    const track = document.createElement("span"); track.className = "dist-track";
    const bar = document.createElement("span"); bar.className = "dist-bar";
    bar.style.width = `${Math.max(counts[k] ? 8 : 0, (100 * counts[k]) / max)}%`;
    const n = document.createElement("span"); n.className = "dist-n"; n.textContent = counts[k];
    track.appendChild(bar);
    row.append(l, track, n);
    box.appendChild(row);
  });
  return box;
}

function firstVisit(game) { return !store.get("seen-" + game); }
function markSeen(game) { store.set("seen-" + game, 1); }

/* ---------- small UI helpers ---------- */
const $ = id => document.getElementById(id);
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

// Shows how long until midnight, updating every minute.
function startCountdown(el) {
  const draw = () => {
    const now = new Date(), next = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    const mins = Math.max(1, Math.ceil((next - now) / 60000));
    el.textContent = `Next puzzle in ${Math.floor(mins / 60)}h ${String(mins % 60).padStart(2, "0")}m`;
  };
  draw();
  clearInterval(el._timer);
  el._timer = setInterval(() => { if (!el.isConnected) clearInterval(el._timer); else draw(); }, 30000);
}

// On phones, results go to the share sheet (Messages, WhatsApp...) instead of the clipboard.
const canShare = !!navigator.share && window.matchMedia && matchMedia("(pointer: coarse)").matches;
function prepareShare(button) {
  if (canShare) button.textContent = button.dataset.label = "Share result";
}

// Copy text to the clipboard from a click; if the browser refuses, select it for the viewer.
async function copyText(button, text, fallbackEl) {
  if (canShare && button.dataset.label === "Share result") {
    try { await navigator.share({ text }); return; }
    catch (err) { if (err && err.name === "AbortError") return; }  // closing the sheet is fine
  }
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
  } catch (err) {
    if (fallbackEl) {
      const sel = window.getSelection(), r = document.createRange();
      r.selectNodeContents(fallbackEl); sel.removeAllRanges(); sel.addRange(r);
    }
    button.textContent = "Selected. Press Ctrl+C to copy";
  }
  setTimeout(() => { if (button.isConnected) button.textContent = button.dataset.label || "Copy"; }, 2500);
}

/* ---------- player career ---------- */
// Team runs in career order, e.g. [["QUE", "1990", "1995"], ["COL", "1995", "2009"]]
function careerRuns(i) {
  const out = [];
  for (const s of P[i].stints) {
    const t = team(s), y = season(s);
    const run = out.find(r => r[0] === t && +r[2] === +y.slice(0, 4));
    if (run) run[2] = y.slice(4);
    else out.push([t, y.slice(0, 4), y.slice(4)]);
  }
  return out.sort((a, b) => a[1] - b[1]);
}
// Teammates with the most seasons together: [[playerIndex, seasons], ...]
function topTeammates(i, n = 3) {
  const counts = new Map();
  for (const s of P[i].stints) for (const o of R[s]) if (o !== i) counts.set(o, (counts.get(o) || 0) + 1);
  return [...counts].sort((a, b) => b[1] - a[1] || P[b[0]].stints.length - P[a[0]].stints.length).slice(0, n);
}
const teammateCount = i => { const s = new Set(); for (const st of P[i].stints) for (const o of R[st]) if (o !== i) s.add(o); return s.size; };

// A small career card: summary line, every team in order, and most frequent teammates.
function careerCard(i) {
  const p = P[i];
  const box = document.createElement("div");
  box.className = "career";
  const teams = new Set(p.stints.map(team)).size;
  const facts = [plural(seasonsOf(i), "season", "seasons"), plural(teams, "team", "teams"), plural(teammateCount(i), "teammate", "teammates")];
  if (p.born) facts.push(`born ${p.born}`);
  const line = document.createElement("p"); line.className = "career-facts"; line.textContent = facts.join(" · ");
  const runs = document.createElement("div"); runs.className = "career-teams";
  careerRuns(i).forEach(([t, a, b]) => {
    const c = document.createElement("span"); c.className = "chip"; c.title = teamName(t);
    c.textContent = `${t} ${a}–${b.slice(2)}`; runs.appendChild(c);
  });
  const mates = document.createElement("p"); mates.className = "career-mates";
  mates.textContent = "Most seasons with: " + topTeammates(i).map(([o, n]) => `${P[o].name} (${n})`).join(", ");
  box.append(line, runs, mates);
  return box;
}

/* ---------- player picker (accessible combobox) ---------- */
// Wires an <input> and an empty <ul> listbox to name search.
// onPick(i) runs when a player is chosen; onType() runs when the text changes.
function makePicker(input, list, { onPick, onType, limit = 8 } = {}) {
  let options = [], active = 0;
  const id = list.id;
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-controls", id);
  input.setAttribute("aria-expanded", "false");
  list.setAttribute("role", "listbox");
  const close = () => { list.hidden = true; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); };
  const draw = () => {
    list.innerHTML = "";
    if (!options.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "No player by that name. Check the spelling, or try just a last name.";
      list.appendChild(li);
    }
    options.forEach((i, n) => {
      const li = document.createElement("li");
      li.id = `${id}-opt-${n}`;
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", n === active ? "true" : "false");
      const name = document.createElement("span"); name.className = "n"; name.textContent = P[i].name;
      const meta = document.createElement("span"); meta.className = "m"; meta.textContent = describe(P[i]);
      li.append(name, meta);
      li.addEventListener("mousedown", e => { e.preventDefault(); choose(i); });
      list.appendChild(li);
    });
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    if (options.length) {
      input.setAttribute("aria-activedescendant", `${id}-opt-${active}`);
      const el = list.children[active];
      if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" });
    }
  };
  const choose = i => { close(); onPick(i); };
  input.addEventListener("input", () => {
    options = search(input.value, limit); active = 0;
    input.value.trim() ? draw() : close();
    if (onType) onType();
  });
  input.addEventListener("keydown", e => {
    if (list.hidden) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (options.length) { active = (active + (e.key === "ArrowDown" ? 1 : -1) + options.length) % options.length; draw(); }
    } else if (e.key === "Enter" && options.length) { e.preventDefault(); choose(options[active]); }
    else if (e.key === "Escape") close();
  });
  input.addEventListener("blur", () => setTimeout(close, 120));
  return {
    // The highlighted option, or the top match if the list is closed (used when Enter submits).
    current: () => options.length ? options[list.hidden ? 0 : active] : null,
    hasText: () => !!input.value.trim(),
    close,
  };
}

/* ---------- page links and data line ---------- */
document.querySelectorAll("nav.site a[data-game]").forEach(a => {
  const done = DAILY_DONE[a.dataset.game];
  if (done && done()) {
    a.classList.add("done");
    a.setAttribute("title", "Today's puzzle is done");
    const s = document.createElement("span"); s.className = "sr"; s.textContent = " (today's puzzle done)";
    a.appendChild(s);
  }
});
const statsLine = document.getElementById("stats");
if (statsLine) statsLine.textContent = `${keys.length.toLocaleString()} team-season rosters · ${P.length.toLocaleString()} players · data updated ${DATA.built}`;

// Offline support and "add to home screen" on the published site.
if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}
