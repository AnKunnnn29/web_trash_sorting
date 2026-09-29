import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test('has no serious accessibility violations on the main screen', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'Accessibility audit runs once in Chromium');
  test.setTimeout(60_000);

  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: async () => {
          const error = new Error('Camera is not needed for accessibility audit');
          error.name = 'NotAllowedError';
          throw error;
        }
      }
    });
    window.tf = {
      loadGraphModel: async () => ({
        execute: () => ({
          data: async () => new Float32Array(31),
          dispose: () => {}
        })
      })
    };
  });
  await page.route('https://cdn.jsdelivr.net/**', route => route.fulfill({
    contentType: 'application/javascript',
    body: ''
  }));
  await page.route('https://fonts.googleapis.com/**', route => route.fulfill({
    contentType: 'text/css',
    body: ''
  }));
  await page.route('https://fonts.gstatic.com/**', route => route.abort());
  await page.goto('/', { waitUntil: 'domcontentloaded' });

  const results = await new AxeBuilder({ page }).analyze();
  const blockingViolations = results.violations.filter(
    violation => violation.impact === 'critical' || violation.impact === 'serious'
  );
  expect(blockingViolations, JSON.stringify(blockingViolations, null, 2)).toEqual([]);

  await page.locator('#btn-mode-toggle').click();
  await page.getByRole('button', { name: /Bắt đầu thực hành/ }).click();
  await page.evaluate(() => window.simulateRFID('battery'));
  const practiceResults = await new AxeBuilder({ page }).analyze();
  const practiceBlockingViolations = practiceResults.violations.filter(
    violation => violation.impact === 'critical' || violation.impact === 'serious'
  );
  expect(
    practiceBlockingViolations,
    JSON.stringify(practiceBlockingViolations, null, 2)
  ).toEqual([]);
});
