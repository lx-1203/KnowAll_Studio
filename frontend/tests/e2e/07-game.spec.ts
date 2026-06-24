import { test, expect } from '@playwright/test'

test.describe('Game Page', () => {
  test('loads and shows game interface', async ({ page }) => {
    page.on('pageerror', err => console.warn('Page error:', err.message))

    await page.goto('/game')
    await page.waitForLoadState('networkidle')

    // Should show game UI
    await expect(page.locator('.ant-card').or(page.locator('.ant-empty')).or(page.locator('text=游戏').or(page.locator('text=Game')))).toBeVisible({ timeout: 15000 })
  })
})
