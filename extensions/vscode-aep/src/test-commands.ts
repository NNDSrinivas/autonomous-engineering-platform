/**
 * Phase 3.3/3.4 UI Test Commands
 * 
 * Add these commands to VS Code extension for immediate UI testing.
 * These bypass the backend and emit Phase 3.3/3.4 events directly.
 */

import * as vscode from 'vscode';

// This file should be imported and used with the naviProvider instance
export function registerTestCommands(naviProvider: any) {

// Test Command 1: Emit ChangePlan
vscode.commands.registerCommand('aep.test.changePlan', () => {
  const changePlan = {
    goal: "Fix path traversal vulnerability in workspace retriever", 
    strategy: "Add comprehensive input validation and path normalization",
    files: [
      {
        path: "backend/agent/perfect_workspace_retriever.py",
        intent: "modify", 
        rationale: "Add path validation to prevent directory traversal"
      },
      {
        path: "tests/test_workspace_retriever.py",
        intent: "create",
        rationale: "Add security tests for path validation"
      }
    ],
    riskLevel: "high",
    testsRequired: true
  };

  // Find active webview and post message
  if (naviProvider?._view) {
    naviProvider.postToWebview({
      type: 'navi.changePlan.generated',
      changePlan
    });
    vscode.window.showInformationMessage('🎯 Test: ChangePlan emitted to UI');
  }
});

// Test Command 2: Emit Diffs
vscode.commands.registerCommand('aep.test.diffs', () => {
  const codeChanges = [
    {
      file_path: "backend/agent/perfect_workspace_retriever.py",
      change_type: "modify",
      diff: `--- a/backend/agent/perfect_workspace_retriever.py
+++ b/backend/agent/perfect_workspace_retriever.py
@@ -25,7 +25,14 @@ def get_file_path(base, user_path):
     Get safe file path within base directory
     """
-    full_path = os.path.join(base, user_path)
+    # Prevent path traversal attacks
+    normalized = os.path.normpath(user_path)
+    if '..' in normalized or normalized.startswith('/'):
+        raise ValueError("Invalid path: potential traversal detected")
+    
+    full_path = os.path.join(base, normalized)
+    resolved = os.path.abspath(full_path)
+    
+    if not resolved.startswith(os.path.abspath(base)):
+        raise ValueError("Path outside base directory")
+    
     return full_path`,
      reasoning: "Add comprehensive path traversal protection"
    }
  ];

  if (naviProvider?._view) {
    naviProvider.postToWebview({
      type: 'navi.diffs.generated', 
      codeChanges
    });
    vscode.window.showInformationMessage('📄 Test: Diffs emitted to UI');
  }
});

// Test Command 3: Emit Validation PASSED
vscode.commands.registerCommand('aep.test.validationPassed', () => {
  const validationResult = {
    status: 'PASSED',
    issues: [],
    canProceed: true
  };

  if (naviProvider?._view) {
    naviProvider.postToWebview({
      type: 'navi.validation.result',
      validationResult
    });
    vscode.window.showInformationMessage('✅ Test: Validation PASSED emitted to UI');
  }
});

// Test Command 4: Emit Validation FAILED
vscode.commands.registerCommand('aep.test.validationFailed', () => {
  const validationResult = {
    status: 'FAILED',
    issues: [
      {
        validator: 'SyntaxValidator',
        file_path: 'backend/agent/perfect_workspace_retriever.py',
        line_number: 42,
        message: 'Python syntax error: missing closing parenthesis'
      },
      {
        validator: 'SecurityValidator', 
        file_path: 'backend/agent/perfect_workspace_retriever.py',
        message: 'Potential SQL injection vulnerability detected'
      }
    ],
    canProceed: false
  };

  if (naviProvider?._view) {
    naviProvider.postToWebview({
      type: 'navi.validation.result',
      validationResult
    });
    vscode.window.showInformationMessage('❌ Test: Validation FAILED emitted to UI');
  }
});

// Test Command 5: Emit Apply Success
vscode.commands.registerCommand('aep.test.applySuccess', () => {
  const applyResult = {
    success: true,
    appliedFiles: [
      {
        file_path: "backend/agent/perfect_workspace_retriever.py",
        operation: "modified",
        success: true
      },
      {
        file_path: "tests/test_workspace_retriever.py",
        operation: "created", 
        success: true
      }
    ],
    summary: {
      totalFiles: 2,
      successfulFiles: 2,
      failedFiles: 0,
      rollbackAvailable: true
    },
    rollbackAvailable: true
  };

  if (naviProvider?._view) {
    naviProvider.postToWebview({
      type: 'navi.changes.applied',
      applyResult
    });
    vscode.window.showInformationMessage('🚀 Test: Apply SUCCESS emitted to UI');
  }
});

// Test Command 6: Full Pipeline Test
vscode.commands.registerCommand('aep.test.fullPipeline', async () => {
  if (!naviProvider?._view) {
    vscode.window.showErrorMessage('Webview not available');
    return;
  }

  vscode.window.showInformationMessage('🧪 Running Phase 3.3/3.4 Full Pipeline Test...');
  
  // Step 1: ChangePlan
  vscode.commands.executeCommand('aep.test.changePlan');
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Step 2: Diffs
  vscode.commands.executeCommand('aep.test.diffs');
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Step 3: Validation FAILED
  vscode.commands.executeCommand('aep.test.validationFailed');
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Step 4: Validation PASSED (after fixes)
  vscode.commands.executeCommand('aep.test.validationPassed');
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Step 5: Apply Success
  vscode.commands.executeCommand('aep.test.applySuccess');
  
  vscode.window.showInformationMessage('✅ Phase 3.3/3.4 Full Pipeline Test Complete!');
});

}

/**
 * Usage:
 * 1. Import and call registerTestCommands(naviProvider) in extension.ts activate() function
 * 2. Run Command Palette → "AEP: Test ChangePlan" etc.
 * 3. Or run "AEP: Test Full Pipeline" for complete sequence
 * 
 * This lets you test the entire Phase 3.3/3.4 UI flow without backend.
 */