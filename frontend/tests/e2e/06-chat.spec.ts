import { test, expect } from '@playwright/test'

test.describe('Chat Page', () => {
  test('loads and shows chat interface', async ({ page }) => {
    page.on('pageerror', err => console.warn('Page error:', err.message))

    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // Should show chat input area
    await expect(page.locator('textarea').or(page.locator('input[type="text"]')).or(page.locator('text=AI').or(page.locator('text=chat')))).toBeVisible({ timeout: 15000 })
  })
})
