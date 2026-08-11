import { expect, test } from '@playwright/test';

async function installBrowserMocks(page, { denyCamera = false } = {}) {
  await page.addInitScript(({ shouldDenyCamera }) => {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: async () => {
          if (shouldDenyCamera) {
            const error = new Error('Permission denied for test');
            error.name = 'NotAllowedError';
            throw error;
          }
          const canvas = document.createElement('canvas');
          canvas.width = 640;
          canvas.height = 480;
          const context = canvas.getContext('2d');
          context.fillStyle = '#12382a';
          context.fillRect(0, 0, canvas.width, canvas.height);
          return canvas.captureStream(5);
        }
      }
    });

    const inputTensor = {
      resizeBilinear: () => inputTensor,
      toFloat: () => inputTensor,
      expandDims: () => inputTensor,
      dispose: () => {}
    };
    window.tf = {
      browser: { fromPixels: () => inputTensor },
      loadGraphModel: async () => ({
        execute: () => ({
          data: async () => new Float32Array(31),
          dispose: () => {}
        })
      })
    };
  }, { shouldDenyCamera: denyCamera });

  await page.route('https://cdn.jsdelivr.net/**', route => route.fulfill({
    contentType: 'application/javascript',
    body: ''
  }));
}

test('completes a simulated sorting round and resets the score', async ({ page }) => {
  await installBrowserMocks(page);
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Cùng phân loại rác nhé!' })).toBeVisible();
  await page.getByRole('button', { name: /Bắt đầu khám phá/ }).click();
  await expect(page.getByRole('heading', { name: 'Đang đợi các bé...' })).toBeVisible();

  await page.evaluate(() => window.simulateRFID('apple'));
  await expect(page.getByRole('heading', { name: /Bé nhận biết được/ })).toBeVisible();
  await page.getByRole('button', { name: /Rác hữu cơ/ }).click();
  await expect(page.getByRole('heading', { name: 'Bé chọn chính xác!' })).toBeVisible();
  await expect(page.locator('#score-correct')).toHaveText('1');
  await expect(page.locator('#score-total')).toHaveText('1');

  await page.locator('#btn-toggle-sim').click();
  await page.getByRole('button', { name: 'Reset điểm số' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Đặt lại điểm' }).click();
  await expect(page.locator('#score-correct')).toHaveText('0');
  await expect(page.locator('#score-total')).toHaveText('0');
});

test('shows an actionable camera permission error', async ({ page }) => {
  await installBrowserMocks(page, { denyCamera: true });
  await page.goto('/');

  await expect(page.locator('#camera-status-message')).toContainText('cấp quyền camera');
  await expect(page.getByRole('button', { name: 'Thử lại camera' })).toBeVisible();
  await expect(page.locator('.camera-container')).toHaveClass(/has-error/);
});

test('does not overflow the mobile viewport', async ({ page }) => {
  await installBrowserMocks(page);
  await page.goto('/');
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth
  }));
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
});
