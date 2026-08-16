import { expect } from '@playwright/test'
import type { Page } from '@playwright/test'

export type ExpectedNavigationLink = {
  label: string
  href: string
}

export async function expectCommonNavigation(
  page: Page,
  expected: ReadonlyArray<ExpectedNavigationLink>,
  exactCount = true,
): Promise<void> {
  const links = page.getByRole('region', { name: '常用' }).getByRole('link')
  if (exactCount) await expect(links).toHaveCount(expected.length)
  for (const [index, item] of expected.entries()) {
    const link = links.nth(index)
    await expect(link).toBeVisible()
    await expect(link).toHaveAccessibleName(item.label)
    await expect(link).toHaveAttribute('href', item.href)
  }
}
