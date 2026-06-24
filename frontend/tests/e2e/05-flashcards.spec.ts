import { test, expect } from '@playwright/test'

test.describe('Flashcard Page', () => {
  test('loads and shows flashcard interface', async ({ page }) => {
    page.on('pageerror', err => console.warn('Page error:', err.message))

    await page.goto('/flashcards')
    await page.waitForLoadState('networkidle')

    // Should show flashcard UI or empty state
    await expect(page.locator('.ant-card').or(page.locator('.ant-empty')).or(page.locator('text=闪卡').or(page.locator('text=Flashcard')))).toBeVisible({ timeout: 15000 })
  })
})
