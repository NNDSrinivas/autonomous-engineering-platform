import { test, expect } from '@playwright/test';

const PLAN_ID = 'presence-plan-1';

async function join(page, userId = 'u-e2e') {
  await page.evaluate(async ([pid, uid]) => {
    await fetch(`/api/plan/${pid}/presence/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: uid,
        email: 'e2e@navralabs.io',
        org_id: 'org-1'
      })
    });
  }, [PLAN_ID, userId]);
}

test('presence appears for two clients, cursor sync works', async ({ browser, baseURL }) => {
  const ctx = await browser.newContext();
  const a = await ctx.newPage();
  const b = await ctx.newPage();

  await a.goto(`${baseURL}/plan/${PLAN_ID}`);
  await b.goto(`${baseURL}/plan/${PLAN_ID}`);

  await join(a, 'u-client-a');
  await join(b, 'u-client-b');

  await expect(a.getByText(/Plan/)).toBeVisible();
  await expect(b.getByText(/Plan/)).toBeVisible();

  // Move mouse on client A
  await a.mouse.move(100, 120);
  await a.mouse.move(140, 160);

  // Heuristic: ghost caret should appear on client B
  // Note: Adjust selector based on actual implementation
  await expect(b.locator('div[title*="u-client-a"]')).toBeVisible({ timeout: 2000 });

  await ctx.close();
});
