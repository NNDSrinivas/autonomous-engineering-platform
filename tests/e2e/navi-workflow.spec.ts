import { test as base, expect, type BrowserContext, type Page } from '@playwright/test';
import { spawn, ChildProcess } from 'child_process';
import { promises as fs } from 'fs';
import path from 'path';

const fetchFn: typeof globalThis.fetch = (...args) => {
  if (!globalThis.fetch) {
    throw new Error('fetch is not available in this environment');
  }
  return globalThis.fetch(...args);
};

// Extend Playwright test with custom fixtures
const test = base.extend<{
  workspaceDir: string;
  backendServer: ChildProcess;
  frontendServer: ChildProcess;
}>({
  workspaceDir: async ({}, use) => {
    // Create temporary workspace for testing
    const tmpDir = path.join(__dirname, '../../tmp', `test-${Date.now()}`);
    await fs.mkdir(tmpDir, { recursive: true });

    // Create sample project structure
    await fs.mkdir(path.join(tmpDir, 'src'));
    await fs.writeFile(
      path.join(tmpDir, 'src', 'app.js'),
      `// Sample application
function calculateTotal(items) {
  let total = 0;
  for (const item of items) {
    total += item.price;
  }
  return total;
}

module.exports = { calculateTotal };`
    );

    await fs.writeFile(
      path.join(tmpDir, 'src', 'utils.js'),
      `// Utility functions
const formatCurrency = (amount) => {
  return '$' + amount.toFixed(2);
};

function validateEmail(email) {
  const regex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
  return regex.test(email);
}

module.exports = { formatCurrency, validateEmail };`
    );

    await fs.writeFile(
      path.join(tmpDir, 'package.json'),
      JSON.stringify({
        name: 'test-project',
        version: '1.0.0',
        description: 'Test project for E2E validation',
        main: 'src/app.js',
        scripts: {
          test: 'jest',
          start: 'node src/app.js'
        },
        dependencies: {
          lodash: '^4.17.21'
        },
        devDependencies: {
          jest: '^29.0.0'
        }
      }, null, 2)
    );

    await use(tmpDir);

    // Clean up temporary workspace
    await fs.rm(tmpDir, { recursive: true, force: true });
  },

  backendServer: async ({}, use) => {
    // Start backend server for testing
    const serverProcess = spawn('python', ['-m', 'uvicorn', 'backend.api.main:app', '--host', '127.0.0.1', '--port', '8788'], {
      cwd: path.join(__dirname, '../../../../'),
      env: {
        ...process.env,
        DATABASE_URL: 'sqlite:////tmp/test_aep.db'
      }
    });

    // Wait for server to start
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Backend server failed to start')), 10000);
      
      const checkServer = async () => {
        try {
          const response = await fetchFn('http://127.0.0.1:8788/health');
          if (response.ok) {
            clearTimeout(timeout);
            resolve(void 0);
          }
        } catch (error) {
          // Server not ready yet
          setTimeout(checkServer, 500);
        }
      };
      
      checkServer();
    });

    await use(serverProcess);

    // Stop server
    serverProcess.kill();
  },

  frontendServer: async ({}, use) => {
    // Start frontend dev server for testing
    const frontendProcess = spawn('npm', ['run', 'dev'], {
      cwd: path.join(__dirname, '../../../../frontend'),
      env: {
        ...process.env,
        PORT: '3001'
      }
    });

    // Wait for frontend to be ready
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Frontend server failed to start')), 15000);
      
      const checkFrontend = async () => {
        try {
          const response = await fetchFn('http://localhost:3001');
          if (response.ok) {
            clearTimeout(timeout);
            resolve(void 0);
          }
        } catch (error) {
          setTimeout(checkFrontend, 1000);
        }
      };
      
      checkFrontend();
    });

    await use(frontendProcess);

    // Stop frontend server
    frontendProcess.kill();
  }
});

test.describe('Navi E2E Workflow Tests', () => {

  test.beforeEach(async ({ page }) => {
    // Set up console logging for debugging
    page.on('console', msg => console.log(`Browser: ${msg.text()}`));
    page.on('pageerror', error => console.error(`Page error: ${error.message}`));
  });

  test('Complete Smart Mode Workflow - Auto Fix', async ({ 
    page, 
    workspaceDir, 
    backendServer, 
    frontendServer 
  }) => {
    // Navigate to Navi frontend
    await page.goto('http://localhost:3001');

    // Verify Navi interface loads
    await expect(page.locator('[data-testid="navi-interface"]')).toBeVisible();

    // Test Smart Workspace Review
    await page.click('[data-testid="smart-workspace-btn"]');
    
    // Wait for workspace analysis to begin
    await expect(page.locator('[data-testid="analysis-progress"]')).toBeVisible();
    
    // Verify progress updates
    await expect(page.locator('[data-testid="analysis-stage"]')).toContainText('Analyzing');
    
    // Wait for analysis completion (timeout: 30s)
    await page.waitForSelector('[data-testid="analysis-complete"]', { timeout: 30000 });
    
    // Verify results display
    await expect(page.locator('[data-testid="analysis-results"]')).toBeVisible();
    await expect(page.locator('[data-testid="files-analyzed"]')).toContainText('2 files');
    
    // Test Auto-Fix Application
    const fixButtons = page.locator('[data-testid="auto-fix-btn"]');
    const fixCount = await fixButtons.count();
    
    if (fixCount > 0) {
      // Click first auto-fix button
      await fixButtons.first().click();
      
      // Verify fix application
      await expect(page.locator('[data-testid="fix-applied"]')).toBeVisible();
      await expect(page.locator('[data-testid="fix-summary"]')).toContainText('Applied');
    }
    
    // Test Undo Functionality
    const undoBtn = page.locator('[data-testid="undo-btn"]');
    if (await undoBtn.isVisible()) {
      await undoBtn.click();
      await expect(page.locator('[data-testid="undo-success"]')).toBeVisible();
    }
  });

  test('Smart Selection Review Workflow', async ({ 
    page, 
    workspaceDir, 
    backendServer, 
    frontendServer 
  }) => {
    await page.goto('http://localhost:3001');

    // Simulate file selection in mock editor
    await page.click('[data-testid="file-selector"]');
    await page.selectOption('[data-testid="file-dropdown"]', 'src/app.js');
    
    // Simulate text selection
    await page.click('[data-testid="text-area"]');
    await page.fill('[data-testid="text-area"]', `function calculateTotal(items) {
  let total = 0;
  for (const item of items) {
    total += item.price;
  }
  return total;
}`);
    
    // Select text
    await page.keyboard.press('Control+a');
    
    // Trigger Smart Selection review
    await page.click('[data-testid="smart-selection-btn"]');
    
    // Wait for selection analysis
    await page.waitForSelector('[data-testid="selection-analysis"]', { timeout: 15000 });
    
    // Verify analysis results
    await expect(page.locator('[data-testid="selection-feedback"]')).toBeVisible();
    await expect(page.locator('[data-testid="suggestions-count"]')).toContainText(/\\d+ suggestions/);
  });

  test('Diff Viewer Interaction Workflow', async ({ 
    page, 
    backendServer, 
    frontendServer 
  }) => {
    await page.goto('http://localhost:3001');

    // Navigate to diff viewer
    await page.click('[data-testid="diff-viewer-tab"]');
    
    // Wait for diff viewer to load
    await expect(page.locator('[data-testid="diff-viewer"]')).toBeVisible();
    
    // Test view mode switching
    await page.click('[data-testid="split-view-btn"]');
    await expect(page.locator('[data-testid="split-view-container"]')).toBeVisible();
    
    await page.click('[data-testid="inline-view-btn"]');
    await expect(page.locator('[data-testid="inline-view-container"]')).toBeVisible();
    
    // Test file navigation in diff viewer
    const fileItems = page.locator('[data-testid="file-tree-item"]');
    const fileCount = await fileItems.count();
    
    if (fileCount > 0) {
      // Click first file
      await fileItems.first().click();
      
      // Verify file content loads
      await expect(page.locator('[data-testid="diff-content"]')).toBeVisible();
      
      // Test hunk interactions
      const hunkItems = page.locator('[data-testid="diff-hunk"]');
      const hunkCount = await hunkItems.count();
      
      if (hunkCount > 0) {
        // Test hunk collapse/expand
        const hunk = hunkItems.first();
        const collapseBtn = hunk.locator('[data-testid="collapse-btn"]');
        
        if (await collapseBtn.isVisible()) {
          await collapseBtn.click();
          await expect(hunk.locator('[data-testid="hunk-content"]')).toBeHidden();
          
          // Expand again
          await collapseBtn.click();
          await expect(hunk.locator('[data-testid="hunk-content"]')).toBeVisible();
        }
        
        // Test Apply button
        const applyBtn = hunk.locator('[data-testid="apply-hunk-btn"]');
        if (await applyBtn.isVisible()) {
          await applyBtn.click();
          await expect(page.locator('[data-testid="hunk-applied"]')).toBeVisible();
        }
        
        // Test Explain button
        const explainBtn = hunk.locator('[data-testid="explain-hunk-btn"]');
        if (await explainBtn.isVisible()) {
          await explainBtn.click();
          
          // Verify explanation modal opens
          await expect(page.locator('[data-testid="explain-modal"]')).toBeVisible();
          await expect(page.locator('[data-testid="explanation-text"]')).not.toBeEmpty();
          
          // Close modal
          await page.click('[data-testid="close-modal-btn"]');
          await expect(page.locator('[data-testid="explain-modal"]')).toBeHidden();
        }
      }
    }
  });

  test('Chat Interface and SSE Streaming', async ({ 
    page, 
    backendServer, 
    frontendServer 
  }) => {
    await page.goto('http://localhost:3001');

    // Test chat interface
    const chatInput = page.locator('[data-testid="chat-input"]');
    await expect(chatInput).toBeVisible();
    
    // Send message
    const testMessage = 'Please review my code and suggest optimizations';
    await chatInput.fill(testMessage);
    await page.click('[data-testid="send-btn"]');
    
    // Verify message appears in chat
    await expect(page.locator('[data-testid="chat-messages"]')).toContainText(testMessage);
    
    // Wait for AI response streaming
    await page.waitForSelector('[data-testid="ai-response"]', { timeout: 20000 });
    
    // Verify streaming progress indicators
    await expect(page.locator('[data-testid="typing-indicator"]')).toBeVisible();
    
    // Wait for response completion
    await page.waitForSelector('[data-testid="response-complete"]', { timeout: 30000 });
    
    // Verify final response
    const response = page.locator('[data-testid="ai-response-text"]');
    await expect(response).not.toBeEmpty();
  });

  test('Attachment Functionality', async ({ 
    page, 
    backendServer, 
    frontendServer 
  }) => {
    await page.goto('http://localhost:3001');

    // Test file attachment
    await page.click('[data-testid="attach-file-btn"]');
    
    // Select file from mock file system
    await page.selectOption('[data-testid="file-selector"]', 'src/app.js');
    await page.click('[data-testid="confirm-attachment"]');
    
    // Verify attachment appears
    await expect(page.locator('[data-testid="attachment-item"]')).toBeVisible();
    await expect(page.locator('[data-testid="attachment-name"]')).toContainText('src/app.js');
    
    // Test attachment removal
    await page.click('[data-testid="remove-attachment-btn"]');
    await expect(page.locator('[data-testid="attachment-item"]')).toBeHidden();
  });

  test('Error Handling and Recovery', async ({ 
    page, 
    backendServer, 
    frontendServer 
  }) => {
    await page.goto('http://localhost:3001');

    // Test backend connection error handling
    // Temporarily stop backend server
    backendServer.kill();
    
    // Attempt operation that requires backend
    await page.click('[data-testid="smart-workspace-btn"]');
    
    // Verify error message displays
    await expect(page.locator('[data-testid="connection-error"]')).toBeVisible();
    await expect(page.locator('[data-testid="error-message"]')).toContainText(/connection/i);
    
    // Test retry functionality
    // Restart backend server (in real test, this would be done differently)
    const newBackendServer = spawn('python', ['-m', 'uvicorn', 'backend.api.main:app', '--host', '127.0.0.1', '--port', '8788']);
    
    // Wait a moment for server restart
    await page.waitForTimeout(3000);
    
    // Click retry button
    await page.click('[data-testid="retry-btn"]');
    
    // Verify operation succeeds after retry
    await expect(page.locator('[data-testid="connection-error"]')).toBeHidden();
    await expect(page.locator('[data-testid="analysis-progress"]')).toBeVisible();
    
    newBackendServer.kill();
  });

  test('Performance and Responsiveness', async ({ 
    page, 
    backendServer, 
    frontendServer 
  }) => {
    await page.goto('http://localhost:3001');

    // Measure page load performance
    const performanceTiming = await page.evaluate(() => {
      return JSON.stringify(performance.timing);
    });
    
    const timing = JSON.parse(performanceTiming);
    const loadTime = timing.loadEventEnd - timing.navigationStart;
    
    // Assert page loads within reasonable time (5 seconds)
    expect(loadTime).toBeLessThan(5000);
    
    // Test interface responsiveness
    const startTime = Date.now();
    
    // Perform multiple rapid interactions
    for (let i = 0; i < 5; i++) {
      await page.click('[data-testid="smart-workspace-btn"]');
      await page.waitForTimeout(100);
      await page.click('[data-testid="cancel-btn"]');
      await page.waitForTimeout(100);
    }
    
    const interactionTime = Date.now() - startTime;
    
    // Assert interactions complete quickly
    expect(interactionTime).toBeLessThan(3000);
  });

  test('Accessibility Compliance', async ({ 
    page, 
    frontendServer 
  }) => {
    await page.goto('http://localhost:3001');

    // Test keyboard navigation
    await page.keyboard.press('Tab');
    
    // Verify focus is visible
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(focusedElement).toBeTruthy();
    
    // Test ARIA labels and roles
    const buttons = page.locator('button');
    const buttonCount = await buttons.count();
    
    for (let i = 0; i < Math.min(buttonCount, 5); i++) {
      const button = buttons.nth(i);
      const ariaLabel = await button.getAttribute('aria-label');
      const textContent = await button.textContent();
      
      // Button should have either aria-label or text content
      expect(ariaLabel || textContent).toBeTruthy();
    }
    
    // Test color contrast (simplified check)
    const styles = await page.evaluate(() => {
      const element = document.querySelector('[data-testid="navi-interface"]');
      if (!element) {
        throw new Error('navi-interface element not found');
      }
      const styles = window.getComputedStyle(element);
      return {
        backgroundColor: styles.backgroundColor,
        color: styles.color
      };
    });
    
    expect(styles.backgroundColor).toBeTruthy();
    expect(styles.color).toBeTruthy();
  });

});

test.describe('Integration Edge Cases', () => {

  test('Large file handling', async ({ 
    page, 
    workspaceDir, 
    backendServer, 
    frontendServer 
  }) => {
    // Create a large test file
    const largeContent = 'console.log("line");\\n'.repeat(10000);
    await fs.writeFile(path.join(workspaceDir, 'src', 'large-file.js'), largeContent);
    
    await page.goto('http://localhost:3001');
    
    // Test analysis of large file
    await page.click('[data-testid="smart-workspace-btn"]');
    
    // Should handle large files without crashing
    await page.waitForSelector('[data-testid="analysis-complete"]', { timeout: 45000 });
    
    // Verify UI remains responsive
    await expect(page.locator('[data-testid="analysis-results"]')).toBeVisible();
  });

  test('Concurrent user sessions', async ({ 
    backendServer, 
    frontendServer,
    browser
  }) => {
    // Test multiple browser contexts simultaneously
    const contexts: BrowserContext[] = await Promise.all([
      browser.newContext(),
      browser.newContext(),
      browser.newContext()
    ]);
    
    const pages: Page[] = await Promise.all(
      contexts.map(context => context.newPage())
    );
    
    // Navigate all pages to Navi
    await Promise.all(
      pages.map(page => page.goto('http://localhost:3001'))
    );
    
    // Perform operations simultaneously
    await Promise.all(
      pages.map(page => page.click('[data-testid="smart-workspace-btn"]'))
    );
    
    // Verify all sessions work correctly
    await Promise.all(
      pages.map(page => 
        expect(page.locator('[data-testid="analysis-progress"]')).toBeVisible()
      )
    );
    
    // Clean up contexts
    await Promise.all(contexts.map(context => context.close()));
  });

});

export { test, expect };
