import { test, expect } from "@playwright/test";

test.describe("Plan Resilience", () => {
  test("resumes after offline and backfills events", async ({ page, context }) => {
    // Navigate to a plan page
    await page.goto("/plan/p1");
    
    // Wait for initial connection
    await expect(page.getByText("Live")).toBeVisible({ timeout: 10000 });
    
    // Go offline
    await context.setOffline(true);
    
    // Verify offline status is shown
    await expect(page.getByText("Offline")).toBeVisible();
    
    // Perform some actions that should queue in outbox
    await page.fill('[placeholder*="step"]', "Test step while offline");
    await page.getByRole('button', { name: /add step/i }).click();
    
    // Should show offline toast
    await expect(page.getByText(/queued your change/i)).toBeVisible();
    
    // Go back online
    await context.setOffline(false);
    
    // Should reconnect and flush outbox
    await expect(page.getByText("Live")).toBeVisible({ timeout: 15000 });
    
    // Should see sync confirmation
    await expect(page.getByText(/synced.*queued changes/i)).toBeVisible({ timeout: 10000 });
    
    // The step should appear in the UI after sync
    await expect(page.getByText("Test step while offline")).toBeVisible({ timeout: 5000 });
  });

  test("shows connection status changes", async ({ page, context }) => {
    await page.goto("/plan/p1");
    
    // Initially should show connecting or live
    await expect(page.locator('[class*="fixed bottom-4 right-4"]')).toBeVisible();
    
    // Go offline
    await context.setOffline(true);
    await expect(page.getByText("Offline")).toBeVisible();
    
    // Go back online  
    await context.setOffline(false);
    await expect(page.getByText(/live|reconnecting/i)).toBeVisible({ timeout: 10000 });
  });

  test("handles rapid offline/online cycles gracefully", async ({ page, context }) => {
    await page.goto("/plan/p1");
    
    // Wait for initial connection
    await expect(page.getByText("Live")).toBeVisible({ timeout: 10000 });
    
    // Rapid offline/online cycles
    for (let i = 0; i < 3; i++) {
      await context.setOffline(true);
      await page.waitForTimeout(100);
      await context.setOffline(false);
      await page.waitForTimeout(200);
    }
    
    // Should eventually reconnect
    await expect(page.getByText("Live")).toBeVisible({ timeout: 15000 });
  });

  test("preserves outbox across page refreshes", async ({ page, context }) => {
    await page.goto("/plan/p1");
    
    // Go offline
    await context.setOffline(true);
    await expect(page.getByText("Offline")).toBeVisible();
    
    // Add a step while offline
    await page.fill('[placeholder*="step"]', "Persistent offline step");
    await page.getByRole('button', { name: /add step/i }).click();
    
    // Refresh the page while still offline
    await page.reload();
    
    // Go back online
    await context.setOffline(false);
    
    // Should still sync the queued step after refresh
    await expect(page.getByText("Live")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/synced.*queued changes/i)).toBeVisible({ timeout: 10000 });
  });

  test("shows appropriate error messages for failed requests", async ({ page }) => {
    // Mock the API to return errors
    await page.route("**/api/plan/*/steps", route => {
      route.fulfill({ status: 500, body: "Server Error" });
    });
    
    await page.goto("/plan/p1");
    await expect(page.getByText("Live")).toBeVisible({ timeout: 10000 });
    
    // Try to add a step - should fail and queue for retry
    await page.fill('[placeholder*="step"]', "Step that will fail");
    await page.getByRole('button', { name: /add step/i }).click();
    
    // Should show error toast
    await expect(page.getByText(/request failed.*retry/i)).toBeVisible();
  });
});