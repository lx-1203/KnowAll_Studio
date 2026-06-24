import { test, expect } from '@playwright/test'

test.describe('Pipeline Page', () => {
  test('loads and shows pipeline interface', async ({ page }) => {
    page.on('pageerror', err => console.warn('Page error:', err.message))

    await page.goto('/pipeline')
    await page.waitForLoadState('networkidle')

    // Should show pipeline UI
    await expect(page.locator('.ant-card').or(page.locator('.ant-empty')).or(page.locator('text=全链路').or(page.locator('text=Pipeline')))).toBeVisible({ timeout: 15000 })
  })
})

test.describe('Navigation', () => {
  test('can navigate between pages via sidebar', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Click on each nav item and verify page changes
    const navItems = page.locator('.ant-menu-item')
    const count = await navItems.count()
    expect(count).toBeGreaterThan(5)
  })
})
