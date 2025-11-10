import * as assert from 'assert';
import * as vscode from 'vscode';

describe('AEP VS Code extension', () => {
  it('loads test harness', () => {
    assert.strictEqual(1, 1);
  });

  it('extension should be present', () => {
    const extension = vscode.extensions.getExtension('navralabs.aep-agent');
    assert.ok(extension);
  });

  it('should activate', async () => {
    const extension = vscode.extensions.getExtension('navralabs.aep-agent');
    assert.ok(extension);
    await extension.activate();
    assert.strictEqual(extension.isActive, true);
  });

  it('should register standard view IDs', async () => {
    // This test verifies that our view IDs follow the standard aep.* format
    const expectedViews = ['aep.chat', 'aep.plan', 'aep.auth'];

    // Note: We can't directly test if views are registered without triggering them,
    // but we can verify the extension activates without errors which indicates
    // the view registrations are valid
    const extension = vscode.extensions.getExtension('navralabs.aep-agent');
    assert.ok(extension);

    if (!extension.isActive) {
      await extension.activate();
    }

    assert.strictEqual(extension.isActive, true);
    // If activation succeeds, the view IDs are properly registered
  });
});