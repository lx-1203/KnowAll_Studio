import { test, expect } from '@playwright/test'

test.describe('Upload Page', () => {
  test('loads and shows upload area', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', err => errors.push(err.message))

    await page.goto('/upload')
    await page.waitForLoadState('networkidle')

    // Should show the page (even without backend, the page should render)
    await expect(page.locator('.ant-upload-drag').or(page.locator('text=上传').or(page.locator('text=Upload')))).toBeVisible({ timeout: 15000 })

    if (errors.filter(e => !e.includes('third-party')).length > 0) console.warn('Errors:', errors)
  })
})
