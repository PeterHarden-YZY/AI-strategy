const { test, expect } = require('@playwright/test');
const path = require('path');

const ARTIFACT_DIR = 'C:/Users/ArthurYoung/.gemini/antigravity-ide/brain/8610541f-b59a-42ec-b4d7-00c1644a7918';

test('verify all web platform features', async ({ page }) => {
  // 1. Verify Run Page & Preset
  await page.goto('http://127.0.0.1:8765/#run');
  await page.waitForSelector('.preset-bar');
  const promoPreset = page.locator('.preset-chip', { hasText: '黑五限时大促' });
  await promoPreset.click();

  // Wait for R0 real-time pre-route computation
  await page.waitForSelector('.adtype-badge.promo', { timeout: 5000 });
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'final_run_promo.png') });

  // 2. Verify Data Contracts: task4 demand signals
  await page.goto('http://127.0.0.1:8765/#data');
  await page.waitForSelector('.datafile-item');
  await page.locator('.datafile-item', { hasText: 'task4_demand_signals.json' }).click();
  await page.locator('.tab', { hasText: '业务载荷' }).click();
  await page.waitForSelector('.trend-svg', { timeout: 5000 });
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'final_task4_trends.png') });

  // 3. Verify Data Contracts: task5 performance
  await page.locator('.datafile-item', { hasText: 'task5_performance.json' }).click();
  await page.locator('.tab', { hasText: '业务载荷' }).click();
  await page.waitForSelector('.kpi-row', { timeout: 5000 });
  await page.waitForSelector('.roas-badge');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'final_task5_kpi.png') });

  // 4. Verify Data Contracts: task6 strategy
  await page.locator('.datafile-item', { hasText: 'task6_strategy.json' }).click();
  await page.locator('.tab', { hasText: '业务载荷' }).click();
  await page.waitForSelector('.fogg-board', { timeout: 5000 });
  await page.waitForSelector('.kano-wrap');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'final_task6_strategy.png') });

  // 5. Verify Data Contracts: task7 creative
  await page.locator('.datafile-item', { hasText: 'task7_creative.json' }).click();
  await page.locator('.tab', { hasText: '业务载荷' }).click();
  await page.waitForSelector('.brief-full-card', { timeout: 5000 });
  await page.waitForSelector('.hook-banner');
  await page.waitForSelector('.shot-table');
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'final_task7_creative.png') });

  // 6. Verify Online JSON Editor Modal
  await page.locator('button', { hasText: '编辑契约' }).click();
  await page.waitForSelector('.editor-modal', { timeout: 5000 });
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'final_json_editor.png') });
  await page.locator('.editor-modal button', { hasText: '取消' }).click();

  // 7. Verify Reports with TOC Navigation
  await page.goto('http://127.0.0.1:8765/#report');
  await page.waitForSelector('.report-toc', { timeout: 5000 });
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'final_report_toc.png') });
});
