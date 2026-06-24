import { test, expect } from '@playwright/test'

test.describe('Knowledge Tree Page', () => {
  test('loads and shows knowledge tree area', async ({ page }) => {
    page.on('pageerror', err => console.warn('Page error:', err.message))

    await page.goto('/knowledge')
    await page.waitForLoadState('networkidle')

    // Page should render with ReactFlow or empty state
    await expect(page.locator('.react-flow').or(page.locator('.ant-empty')).or(page.locator('text=知识树').or(page.locator('text=Knowledge')))).toBeVisible({ timeout: 15000 })
  })
})
