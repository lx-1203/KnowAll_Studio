import { test, expect } from '@playwright/test'

test.describe('Settings Page', () => {
  test('loads and shows settings form', async ({ page }) => {
    page.on('pageerror', err => console.warn('Page error:', err.message))

    await page.goto('/settings')
    await page.waitForLoadState('networkidle')

    // Should show settings card
    await expect(page.locator('.ant-card').or(page.locator('text=设置').or(page.locator('text=Settings')))).toBeVisible({ timeout: 15000 })
  })
})
