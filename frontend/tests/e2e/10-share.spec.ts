import { test, expect } from '@playwright/test'

test.describe('Share Page', () => {
  test('loads and shows share interface', async ({ page }) => {
    page.on('pageerror', err => console.warn('Page error:', err.message))

    await page.goto('/share')
    await page.waitForLoadState('networkidle')

    // Should show share UI
    await expect(page.locator('.ant-card').or(page.locator('.ant-empty')).or(page.locator('text=Share').or(page.locator('text=分享')))).toBeVisible({ timeout: 15000 })
  })
})
