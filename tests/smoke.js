// Browser test for the built site in docs/. Plays every page the way a person would.
// Run: node tests/smoke.js   (needs Playwright: npm i playwright && npx playwright install chromium)
const http = require("http");
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const DOCS = path.join(__dirname, "..", "docs");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".webmanifest": "application/manifest+json", ".woff2": "font/woff2", ".xml": "application/xml", ".txt": "text/plain" };
let failures = 0;
const check = (ok, what) => { console.log(`${ok ? "  ok  " : "  FAIL"} ${what}`); if (!ok) failures++; };

function serve() {
  const server = http.createServer((req, res) => {
    let file = decodeURIComponent(req.url.split("?")[0].split("#")[0]);
    if (file.endsWith("/")) file += "index.html";
    const full = path.join(DOCS, file);
    if (!full.startsWith(DOCS) || !fs.existsSync(full)) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { "Content-Type": TYPES[path.extname(full)] || "application/octet-stream" });
    fs.createReadStream(full).pipe(res);
  });
  return new Promise(resolve => server.listen(0, "127.0.0.1", () => resolve(server)));
}

(async () => {
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}/`;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 1400 } });
  // Keep the test offline-safe: fonts are optional.
  await ctx.route(/fonts\.(googleapis|gstatic)\.com/, r => r.abort());
  const errors = [];
  const open = async (file) => {
    const page = await ctx.newPage();
    page.on("pageerror", e => errors.push(`${file}: ${e.message}`));
    page.on("console", m => { if (m.type() === "error" && !/fonts|ERR_FAILED/.test(m.text())) errors.push(`${file}: ${m.text()}`); });
    await page.goto(base + file);
    await page.waitForTimeout(300);
    return page;
  };

  console.log("Find a connection");
  let p = await open("index.html");
  check((await p.locator("nav.site a").count()) === 5, "five page links");
  check(/^\d+$/.test((await p.locator(".verdict .big").innerText()).trim()), "opens on an example connection");
  await p.fill("#a", "gretzky"); await p.waitForTimeout(50);
  check((await p.locator("#a-list li .n").first().innerText()) === "Wayne Gretzky", "suggestions find Wayne Gretzky");
  await p.keyboard.press("Enter");
  await p.fill("#b", "crosby"); await p.waitForTimeout(50); await p.keyboard.press("Enter");
  await p.click("#go"); await p.waitForTimeout(100);
  check((await p.locator(".chain .player").count()) >= 2, "connects Gretzky and Crosby");
  check(await p.isVisible(".copy-link"), "copy link button");
  await p.locator(".player:not(.end) .career-toggle").first().click(); await p.waitForTimeout(50);
  check(/seasons? · \d+ teams?/.test(await p.locator(".career-facts").first().innerText()), "career details open");
  await p.locator('.player:not(.end) button:has-text("Route around")').first().click(); await p.waitForTimeout(100);
  check(await p.isVisible("#avoiding"), "route around a player");
  check((await p.locator("#today-grid .game").count()) === 4, "today's puzzles shows four games");
  await p.click("#random"); await p.waitForTimeout(100);
  check((await p.locator(".chain .player").count()) >= 2, "random pair");

  console.log("Build the Chain");
  p = await open("chain.html");
  check(/Daily puzzle #\d+/i.test(await p.textContent("#eyebrow")), "daily puzzle loads");
  check(await p.evaluate(() => document.getElementById("how").open), "how to play opens on a first visit");
  const wrong = await p.evaluate(() => { for (let i = 0; i < P.length; i++) if (!shared(G.a, i).length && i !== G.b && P[i].stints.length > 10) return P[i].name; });
  await p.fill("#g", wrong); await p.waitForTimeout(50); await p.keyboard.press("Enter"); await p.waitForTimeout(50);
  check((await p.innerText("#feedback")).startsWith("No."), "a wrong teammate is a miss");
  await p.click("#hint");
  check((await p.innerText("#feedback")).startsWith("Hint"), "hint");
  const path_ = await p.evaluate(() => shortestPath(G.a, G.b));
  for (const i of path_.slice(1, -1)) {
    const name = await p.evaluate(i => P[i].name, i);
    if (await p.evaluate(() => G.done)) break;
    await p.fill("#g", name); await p.waitForTimeout(40);
    // pick the exact player (namesakes exist), using the list
    const idx = await p.evaluate(i => search(P[i].name).indexOf(i), i);
    for (let k = 0; k < idx; k++) await p.keyboard.press("ArrowDown");
    await p.keyboard.press("Enter"); await p.waitForTimeout(40);
  }
  check(await p.isVisible("#result"), "solving shows the result");
  check(/Perfect/i.test(await p.textContent("#result h2")), "matching par is a perfect chain");
  check(/Next puzzle in \d+h/.test(await p.innerText("#result .countdown")), "countdown to the next puzzle");
  await p.reload(); await p.waitForTimeout(300);
  check(await p.evaluate(() => G.done), "progress is saved");
  check(await p.locator('nav.site a[data-game="chain"].done').count() === 1, "page link shows today's puzzle is done");
  check(await p.locator(".dist-row.today").count() === 1, "results history highlights today");
  await p.click("#mode-practice"); await p.click("#giveup"); await p.waitForTimeout(50);
  check(await p.isVisible("#result"), "practice and give up");

  console.log("Mystery Player");
  p = await open("mystery.html");
  check((await p.locator("#clues li:not(.locked)").count()) === 1, "starts with one clue");
  const notIt = await p.evaluate(() => P[POOLS.easy.find(i => i !== S.m)].name);
  await p.fill("#g", notIt); await p.waitForTimeout(50); await p.keyboard.press("Enter"); await p.waitForTimeout(50);
  check((await p.locator("#clues li:not(.locked)").count()) === 2, "a wrong guess unlocks a clue");
  check((await p.locator(".g-row .fact").count()) >= 4, "wrong guess shows comparisons");
  await p.evaluate(() => guess(S.m)); await p.waitForTimeout(50);
  check(/Solved with 2 of 7/.test(await p.innerText("#share-text")), "solving shows the share text");

  console.log("Who Played Longer?");
  p = await open("longer.html");
  for (let k = 0; k < 10; k++) { await p.click("#card-0"); await p.click("#next"); }
  check(/\d+\/10/.test(await p.innerText("#result .big")), "daily 10 finishes with a score");
  await p.click("#mode-endless");
  for (let k = 0; k < 5; k++) {
    const side = await p.evaluate(() => { const { stat, pair } = current(); return value(stat, pair[0]) > value(stat, pair[1]) ? 0 : 1; });
    await p.click("#card-" + side); await p.click("#next");
  }
  check(await p.evaluate(() => E.streak === 5), "endless streak counts");

  console.log("Name the Roster");
  p = await open("roster.html");
  await p.click("#start");
  const surname = await p.evaluate(() => { const i = G.roster.find(i => G.roster.filter(j => P[j].lasts.some(l => P[i].lasts.includes(l))).length === 1); return P[i].lasts[P[i].lasts.length - 1]; });
  await p.type("#g", surname, { delay: 10 }); await p.waitForTimeout(50);
  check((await p.innerText("#count")).startsWith("1/"), `typing a last name (${surname}) fills it in`);
  await p.fill("#g", "zzzz"); await p.keyboard.press("Enter");
  check(/No player/.test(await p.innerText("#feedback")), "unknown name is a miss");
  await p.click("#done");
  check(await p.isVisible("#result") && (await p.locator(".slot.missed").count()) > 0, "finishing shows everyone missed");

  console.log("Main page after playing");
  p = await open("index.html");
  check(/✓/.test(await p.locator('.game[href="chain.html"]').innerText()), "today's puzzles shows the chain as done");
  check(/✓/.test(await p.locator('.game[href="longer.html"]').innerText()), "today's puzzles shows the daily 10 as done");

  console.log("Missing page");
  const r = await (await ctx.newPage()).goto(base + "404.html");
  check(r.status() === 200, "404 page exists");

  console.log("Phone layout");
  const phone = await browser.newContext({ viewport: { width: 390, height: 900 }, colorScheme: "dark" });
  await phone.route(/fonts\.(googleapis|gstatic)\.com/, r => r.abort());
  for (const file of ["index.html", "chain.html", "mystery.html", "longer.html", "roster.html"]) {
    const m = await phone.newPage();
    m.on("pageerror", e => errors.push(`${file} (phone): ${e.message}`));
    await m.goto(base + file); await m.waitForTimeout(250);
    check(!(await m.evaluate(() => document.documentElement.scrollWidth > innerWidth)), `${file} fits a phone screen`);
  }

  check(errors.length === 0, "no script errors" + (errors.length ? ":\n    " + errors.join("\n    ") : ""));
  await browser.close();
  server.close();
  console.log(failures ? `\n${failures} check(s) failed` : "\nAll checks passed");
  process.exit(failures ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
