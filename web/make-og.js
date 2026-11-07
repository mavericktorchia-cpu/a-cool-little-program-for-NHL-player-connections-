// Renders web/og-card.html to docs/og.png (1200x630). Needs Playwright: npm i playwright
const path = require("path");
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
  await page.goto("file://" + path.join(__dirname, "og-card.html"));
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(__dirname, "..", "docs", "og.png") });
  await browser.close();
})();
