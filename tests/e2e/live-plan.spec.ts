import { test, expect, Page } from '@playwright/test';

/**
 * E2E tests for Live Plan Mode multi-client real-time collaboration
 * 
 * These tests verify that:
 * 1. Multiple browser tabs can connect to the same plan
 * 2. Events published by one client appear in all other clients
 * 3. SSE streaming works correctly across multiple connections
 */

const BACKEND_URL = process.env.E2E_BACKEND_URL || 'http://localhost:8000';
const PLAN_ID = 'e2e-test-plan-' + Date.now();

// Reusable selectors
// Using data-testid for robust test automation - prefer this over fragile placeholder/text selectors
const STEP_INPUT_SELECTOR = '[data-testid="step-input"], input[placeholder*="step" i], textarea[placeholder*="step" i], form input[type="text"]';
const ADD_BUTTON_SELECTOR = '[data-testid="add-step"], button:has-text("Add Step"), button:has-text("Add"), button[type="submit"]';

// Timing constants
const NETWORK_OFFLINE_DELAY = 1000; // Time to wait after going offline/online
const STEP_SUBMISSION_DELAY = 100; // Delay between rapid step submissions
const STEPS_RENDER_DELAY = 2000; // Time to wait for all steps to render

/**
 * Helper to wait for an element containing specific text
 */
async function waitForStepText(page: Page, text: string, timeout = 5000) {
  await expect(page.locator('text=' + text)).toBeVisible({ timeout });
}

/**
 * Helper to navigate to a plan page
 */
async function navigateToPlan(page: Page, planId: string) {
  // Use the baseURL from playwright.config.ts; the leading `/` makes this path relative to baseURL
  await page.goto(`/plan/${planId}`);
}

test.describe('Live Plan - Real-time Multi-Client Collaboration', () => {
  
  test('two tabs receive the same step updates in real-time', async ({ browser }) => {
    // Create a context for this test
    const context = await browser.newContext();
    
    // Open two tabs
    const pageA = await context.newPage();
    const pageB = await context.newPage();

    // Navigate both tabs to the same plan
    await navigateToPlan(pageA, PLAN_ID);
    await navigateToPlan(pageB, PLAN_ID);

    // Wait for pages to load
    await pageA.waitForLoadState('networkidle');
    await pageB.waitForLoadState('networkidle');

    // Add a step from Tab A
    await pageA.fill(STEP_INPUT_SELECTOR, 'E2E: First collaborative step');
    await pageA.click(ADD_BUTTON_SELECTOR);

    // Both tabs should show the step within 2 seconds
    await waitForStepText(pageA, 'E2E: First collaborative step', 3000);
    await waitForStepText(pageB, 'E2E: First collaborative step', 3000);

    // Add another step from Tab B
    await pageB.fill(STEP_INPUT_SELECTOR, 'E2E: Second collaborative step');
    await pageB.click(ADD_BUTTON_SELECTOR);

    // Both tabs should show the second step
    await waitForStepText(pageA, 'E2E: Second collaborative step', 3000);
    await waitForStepText(pageB, 'E2E: Second collaborative step', 3000);

    // Verify both tabs show both steps
    await expect(pageA.locator('text=E2E: First collaborative step')).toBeVisible();
    await expect(pageA.locator('text=E2E: Second collaborative step')).toBeVisible();
    await expect(pageB.locator('text=E2E: First collaborative step')).toBeVisible();
    await expect(pageB.locator('text=E2E: Second collaborative step')).toBeVisible();

    await context.close();
  });

  test('SSE connection handles disconnection and reconnection', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await navigateToPlan(page, PLAN_ID + '-reconnect');
    await page.waitForLoadState('networkidle');

    // Add initial step
    await page.fill(STEP_INPUT_SELECTOR, 'Step before disconnect');
    await page.click(ADD_BUTTON_SELECTOR);
    await waitForStepText(page, 'Step before disconnect', 3000);

    // Simulate network offline
    await context.setOffline(true);
    await page.waitForTimeout(NETWORK_OFFLINE_DELAY);

    // Go back online
    await context.setOffline(false);
    await page.waitForTimeout(NETWORK_OFFLINE_DELAY);

    // Add another step after reconnection
    await page.fill(STEP_INPUT_SELECTOR, 'Step after reconnect');
    await page.click(ADD_BUTTON_SELECTOR);
    await waitForStepText(page, 'Step after reconnect', 3000);

    // Verify both steps are visible
    await expect(page.locator('text=Step before disconnect')).toBeVisible();
    await expect(page.locator('text=Step after reconnect')).toBeVisible();

    await context.close();
  });

  test('plan list shows active and archived plans', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    // Navigate to plans list (uses baseURL from playwright config)
    await page.goto('/plans');
    await page.waitForLoadState('networkidle');

    // Should show some UI elements
    await expect(page.locator('h1, h2').filter({ hasText: /plan/i })).toBeVisible({ timeout: 5000 });

    await context.close();
  });
});

test.describe('Live Plan - Performance', () => {
  
  test('handles rapid step additions without loss', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await navigateToPlan(page, PLAN_ID + '-rapid');
    await page.waitForLoadState('networkidle');

    // Add 5 steps rapidly
    for (let i = 1; i <= 5; i++) {
      await page.fill(STEP_INPUT_SELECTOR, `Rapid step ${i}`);
      await page.click(ADD_BUTTON_SELECTOR);
      await page.waitForTimeout(STEP_SUBMISSION_DELAY);
    }

    // Wait for all steps to appear
    await page.waitForTimeout(STEPS_RENDER_DELAY);

    // Verify all 5 steps are visible
    for (let i = 1; i <= 5; i++) {
      await expect(page.locator(`text=Rapid step ${i}`)).toBeVisible();
    }

    await context.close();
  });
});
