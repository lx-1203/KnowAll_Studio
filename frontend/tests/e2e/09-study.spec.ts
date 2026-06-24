import { test, expect } from '@playwright/test'

test.describe('Study Plan Page', () => {
  test('loads and shows study plan interface', async ({ page }) => {
    page.on('pageerror', err => console.warn('Page error:', err.message))

    await page.goto('/study')
    await page.waitForLoadState('networkidle')

    // Should show study plan UI
    await expect(page.locator('.ant-card').or(page.locator('.ant-empty')).or(page.locator('text=Study').or(page.locator('text=学习计划')))).toBeVisible({ timeout: 15000 })
  })
})
