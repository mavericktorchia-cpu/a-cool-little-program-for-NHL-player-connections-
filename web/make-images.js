// Renders the link-preview image (docs/og.png) and the app icons (web/icons/*.png).
// Needs Playwright: npm i playwright. Run: node web/make-images.js
const path = require("path");
const { chromium } = require("playwright");

const puck = (size, pad) => `<!doctype html><html><body style="margin:0;background:transparent">
<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 64 64">
  ${pad ? '<rect width="64" height="64" fill="#0d1b2a"/>' : ""}
  <g transform="translate(32 32) scale(${pad ? 0.62 : 0.94}) translate(-32 -32)">
    <circle cx="32" cy="32" r="30" fill="#c8102e"/>
    <rect x="29" y="2" width="6" height="60" fill="#fff"/>
    <circle cx="32" cy="32" r="10" fill="none" stroke="#fff" stroke-width="5"/>
  </g>
</svg></body></html>`;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
  await page.goto("file://" + path.join(__dirname, "og-card.html"));
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(__dirname, "..", "docs", "og.png") });

  // [file, size, solid background (needed for maskable and Apple icons)]
  for (const [file, size, solid] of [
    ["icon-192.png", 192, false], ["icon-512.png", 512, false],
    ["icon-maskable-512.png", 512, true], ["apple-touch-icon.png", 180, true],
  ]) {
    const p = await browser.newPage({ viewport: { width: size, height: size } });
    await p.setContent(puck(size, solid));
    await p.screenshot({ path: path.join(__dirname, "icons", file), omitBackground: !solid });
    await p.close();
  }
  await browser.close();
})();
