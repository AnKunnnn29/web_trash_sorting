import fs from 'node:fs';
import { expect, test } from '@playwright/test';

test('loads the bundled TF.js model and performs a real browser inference', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'One real inference is enough for the browser smoke test');
  test.setTimeout(120_000);

  const tfBundle = fs.readFileSync(
    'node_modules/@tensorflow/tfjs/dist/tf.min.js',
    'utf8'
  );
  await page.route('https://cdn.jsdelivr.net/**', route => {
    const body = route.request().url().includes('/@tensorflow/tfjs@4.20.0/')
      ? tfBundle
      : '';
    route.fulfill({ contentType: 'application/javascript', body });
  });
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: async () => {
          const error = new Error('No camera required for the model smoke test');
          error.name = 'NotAllowedError';
          throw error;
        }
      }
    });
  });

  await page.goto('/');
  await expect(page.locator('#ai-status-text')).toHaveText('⚡ AI trình duyệt sẵn sàng', {
    timeout: 60_000
  });

  const result = await page.evaluate(async () => {
    const canvas = document.createElement('canvas');
    canvas.width = 224;
    canvas.height = 224;
    const context = canvas.getContext('2d');
    context.fillStyle = '#e4e0d8';
    context.fillRect(0, 0, 224, 224);
    context.fillStyle = '#b92d25';
    context.fillRect(82, 28, 60, 170);

    const model = await window.tf.loadGraphModel('/tfjs_model/model.json');
    const input = window.tf.browser.fromPixels(canvas)
      .resizeBilinear([224, 224])
      .toFloat()
      .expandDims(0);
    const output = model.execute(input);
    const probabilities = Array.from(await output.data());
    const labels = await fetch('/tfjs_model/labels.json').then(response => response.json());
    const bestIndex = probabilities.indexOf(Math.max(...probabilities));
    input.dispose();
    output.dispose();
    model.dispose();
    return {
      outputCount: probabilities.length,
      probabilitySum: probabilities.reduce((sum, value) => sum + value, 0),
      label: labels[bestIndex],
      confidence: probabilities[bestIndex]
    };
  });

  expect(result.outputCount).toBe(31);
  expect(result.probabilitySum).toBeCloseTo(1, 3);
  expect(result.label).toBeTruthy();
  expect(result.confidence).toBeGreaterThan(0);
  expect(result.confidence).toBeLessThanOrEqual(1);
  testInfo.annotations.push({
    type: 'real-inference',
    description: `${result.label} at ${(result.confidence * 100).toFixed(1)}%`
  });
});
