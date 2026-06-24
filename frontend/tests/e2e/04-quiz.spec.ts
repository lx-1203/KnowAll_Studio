import { test, expect } from '@playwright/test'

test.describe('Quiz Page', () => {
  test('loads and shows quiz interface', async ({ page }) => {
    page.on('pageerror', err => console.warn('Page error:', err.message))

    await page.goto('/quiz')
    await page.waitForLoadState('networkidle')

    // Page should render quiz UI or empty state
    await expect(page.locator('.ant-card').or(page.locator('text=quiz').or(page.locator('text=Quiz')).or(page.locator('text=题库')))).toBeVisible({ timeout: 15000 })
  })
})
