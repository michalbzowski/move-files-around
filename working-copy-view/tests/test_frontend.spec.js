// Uruchamiaj z Playwright CLI: npx playwright test
const { test, expect } = require('@playwright/test');

test('powinien filtrować pliki po rozszerzeniach i otwierać modal miniatury', async ({ page }) => {
  await page.goto('http://localhost:5001/');
  // Rozwiń multiselect i wybierz np. jpg -- choices ukrywa oryginalny element - dlatego workaroundd
  await page.click('.choices__inner'); // albo inny selektor wskazujący kontener Choices

  await page.click('text=/jpg/i');
  await page.click('button:has-text("Filtruj")');
  // Sprawdź, że pojawiły się tylko pliki jpg (np. liczbę w tabeli)
  const komorki = await page.locator('table#filesTable tbody tr').count();
  expect(komorki).toBeGreaterThan(0);

  // Kliknij w pierwszy podgląd obrazka — otwiera się modal
  await page.click('img.preview');
  await expect(page.locator('#imageModal')).toHaveClass(/is-active/);

  // Zamknij modal
  await page.click('#imageModal .modal-close');
  await expect(page.locator('#imageModal')).not.toHaveClass(/is-active/);
});
