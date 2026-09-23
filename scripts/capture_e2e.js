const { chromium } = require('playwright');
const path = require('path');

const ARTIFACT_DIR = 'C:/Users/ArthurYoung/.gemini/antigravity-ide/brain/8610541f-b59a-42ec-b4d7-00c1644a7918';

async function run() {
  console.log('Launching Chrome browser...');
  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  console.log('1. Testing Run Page and Presets...');
  await page.goto('http://127.0.0.1:8765/#run');
  await page.waitForSelector('.preset-bar');
  // Click preset
  const promoPreset = page.locator('.preset-chip', { hasText: '黑五限时大促' });
  await promoPreset.click();
  // Wait for R0 pre-route to compute
  await page.waitForSelector('.adtype-badge.promo');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'e2e_run_preroute.png') });
  console.log('Saved e2e_run_preroute.png');

  console.log('2. Testing Data Contracts: task4 demand signals...');
  await page.goto('http://127.0.0.1:8765/#data');
  await page.waitForSelector('.datafile-item');
  await page.locator('.datafile-item', { hasText: 'task4_demand_signals.json' }).click();
  await page.locator('.tab', { hasText: '业务载荷' }).click();
  await page.waitForSelector('.trend-svg');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'e2e_data_task4_trends.png') });
  console.log('Saved e2e_data_task4_trends.png');

  console.log('3. Testing Data Contracts: task5 performance...');
  await page.locator('.datafile-item', { hasText: 'task5_performance.json' }).click();
  await page.locator('.tab', { hasText: '业务载荷' }).click();
  await page.waitForSelector('.kpi-row');
  await page.waitForSelector('.roas-badge');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'e2e_data_task5_kpi.png') });
  console.log('Saved e2e_data_task5_kpi.png');

  console.log('4. Testing Data Contracts: task6 strategy...');
  await page.locator('.datafile-item', { hasText: 'task6_strategy.json' }).click();
  await page.locator('.tab', { hasText: '业务载荷' }).click();
  await page.waitForSelector('.fogg-board');
  await page.waitForSelector('.kano-wrap');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'e2e_data_task6_strategy.png') });
  console.log('Saved e2e_data_task6_strategy.png');

  console.log('5. Testing Data Contracts: task7 creative...');
  await page.locator('.datafile-item', { hasText: 'task7_creative.json' }).click();
  await page.locator('.tab', { hasText: '业务载荷' }).click();
  await page.waitForSelector('.brief-full-card');
  await page.waitForSelector('.hook-banner');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'e2e_data_task7_creative.png') });
  console.log('Saved e2e_data_task7_creative.png');

  console.log('6. Testing Online JSON Contract Editor...');
  await page.locator('button', { hasText: '编辑契约' }).click();
  await page.waitForSelector('.editor-modal');
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'e2e_json_editor.png') });
  console.log('Saved e2e_json_editor.png');
  await page.locator('.editor-modal button', { hasText: '取消' }).click();

  console.log('7. Testing Report Page with TOC Navigation...');
  await page.goto('http://127.0.0.1:8765/#report');
  await page.waitForSelector('.report-toc');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'e2e_report_toc.png') });
  console.log('Saved e2e_report_toc.png');

  console.log('All end-to-end verifications completed successfully!');
  await browser.close();
}

run().catch((err) => {
  console.error('E2E Verification failed:', err);
  process.exit(1);
});
