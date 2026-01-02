import * as vscode from 'vscode';
import { smartModeSSEClient, SmartModeResult } from '../sse/smartModeClient';
import { undoManager } from '../repo/undoManager';
import { applyUnifiedPatch } from '../repo/applyPatch';

export interface SmartModeOptions {
  files?: string[];
  instruction?: string;
  diffContent?: string;
  autoApply?: boolean;
  confidence?: number;
}

export class SmartModeCommands {
  private outputChannel: vscode.OutputChannel;

  constructor() {
    this.outputChannel = vscode.window.createOutputChannel('Navi Smart Mode');
  }

  /**
   * Register all Smart Mode commands
   */
  public registerCommands(context: vscode.ExtensionContext): void {
    // Smart Review Workspace command
    const smartReviewWorkspace = vscode.commands.registerCommand(
      'aep.navi.smartReviewWorkspace',
      () => this.smartReviewWorkspace()
    );

    // Smart Review Selection command
    const smartReviewSelection = vscode.commands.registerCommand(
      'aep.navi.smartReviewSelection',
      () => this.smartReviewSelection()
    );

    // Smart Review with Custom Instruction
    const smartReviewWithInstruction = vscode.commands.registerCommand(
      'aep.navi.smartReviewWithInstruction',
      () => this.smartReviewWithInstruction()
    );

    // Apply Smart Diff (from existing diff)
    const applySmartDiff = vscode.commands.registerCommand(
      'aep.navi.applySmartDiff',
      (diffContent: string) => this.applySmartDiff(diffContent)
    );

    // Undo Last Smart Mode Operation
    const undoSmartMode = vscode.commands.registerCommand(
      'aep.navi.undoSmartMode',
      () => this.undoLastSmartMode()
    );

    // Smart Mode Settings
    const smartModeSettings = vscode.commands.registerCommand(
      'aep.navi.smartModeSettings',
      () => this.openSmartModeSettings()
    );

    context.subscriptions.push(
      smartReviewWorkspace,
      smartReviewSelection,
      smartReviewWithInstruction,
      applySmartDiff,
      undoSmartMode,
      smartModeSettings
    );
  }

  /**
   * Smart Review Workspace - analyze and potentially auto-apply changes to entire workspace
   */
  public async smartReviewWorkspace(): Promise<SmartModeResult | undefined> {
    try {
      // Get all relevant files in workspace
      const workspaceFiles = await this.getWorkspaceFiles();

      if (workspaceFiles.length === 0) {
        vscode.window.showInformationMessage('No suitable files found in workspace for Smart Mode analysis.');
        return;
      }

      this.outputChannel.appendLine(`🔍 Smart Review Workspace: ${workspaceFiles.length} files`);

      // Run Smart Mode analysis
      const result = await smartModeSSEClient.connectReviewStream(
        workspaceFiles,
        '', // No initial diff
        'Analyze workspace and suggest improvements', // Default instruction
        0.8 // High confidence for workspace analysis
      );

      this.outputChannel.appendLine(`✅ Smart Review completed: ${result.mode} mode used`);

      return result;

    } catch (error) {
      this.outputChannel.appendLine(`❌ Smart Review Workspace failed: ${error}`);
      vscode.window.showErrorMessage(`Smart Review failed: ${error}`);
    }
  }

  /**
   * Smart Review Selection - analyze selected files or current file
   */
  public async smartReviewSelection(): Promise<SmartModeResult | undefined> {
    try {
      const activeEditor = vscode.window.activeTextEditor;

      if (!activeEditor) {
        vscode.window.showWarningMessage('No active file to review. Please open a file first.');
        return;
      }

      const currentFile = activeEditor.document.uri.fsPath;
      const files = [currentFile];

      this.outputChannel.appendLine(`🎯 Smart Review Selection: ${currentFile}`);

      // Get any selected text for context
      const selection = activeEditor.selection;
      let instruction = 'Review and optimize this file';

      if (!selection.isEmpty) {
        const selectedText = activeEditor.document.getText(selection);
        instruction = `Review and optimize the selected code: ${selectedText.substring(0, 200)}...`;
      }

      const result = await smartModeSSEClient.connectReviewStream(
        files,
        '', // No diff content for file analysis
        instruction,
        0.7 // Medium confidence for single file
      );

      this.outputChannel.appendLine(`✅ Smart Review Selection completed: ${result.mode} mode`);

      return result;

    } catch (error) {
      this.outputChannel.appendLine(`❌ Smart Review Selection failed: ${error}`);
      vscode.window.showErrorMessage(`Smart Review failed: ${error}`);
    }
  }

  /**
   * Smart Review with Custom Instruction - let user specify what to do
   */
  public async smartReviewWithInstruction(): Promise<SmartModeResult | undefined> {
    try {
      // Get custom instruction from user
      const instruction = await vscode.window.showInputBox({
        prompt: 'Enter your instruction for Smart Mode',
        placeHolder: 'e.g., "Add error handling to all functions", "Optimize for performance", "Add TypeScript types"',
        value: '',
      });

      if (!instruction) {
        return; // User cancelled
      }

      // Get target files (workspace or selection)
      const scopeChoice = await vscode.window.showQuickPick([
        {
          label: '📁 Entire Workspace',
          description: 'Apply instruction to all relevant files in workspace',
          detail: 'Smart Mode will analyze and apply changes across the project'
        },
        {
          label: '📄 Current File Only',
          description: 'Apply instruction to the currently open file',
          detail: 'Smart Mode will focus on the active editor file'
        },
        {
          label: '🎯 Selected Files',
          description: 'Choose specific files to target',
          detail: 'Smart Mode will let you pick which files to analyze'
        }
      ], {
        placeHolder: 'Choose scope for Smart Mode instruction'
      });

      if (!scopeChoice) {
        return; // User cancelled
      }

      let targetFiles: string[] = [];

      switch (scopeChoice.label) {
        case '📁 Entire Workspace':
          targetFiles = await this.getWorkspaceFiles();
          break;

        case '📄 Current File Only':
          const activeEditor = vscode.window.activeTextEditor;
          if (!activeEditor) {
            vscode.window.showWarningMessage('No active file open.');
            return;
          }
          targetFiles = [activeEditor.document.uri.fsPath];
          break;

        case '🎯 Selected Files':
          targetFiles = await this.selectTargetFiles();
          break;
      }

      if (targetFiles.length === 0) {
        vscode.window.showWarningMessage('No files selected for Smart Mode.');
        return;
      }

      this.outputChannel.appendLine(`🚀 Smart Mode Custom Instruction: "${instruction}"`);
      this.outputChannel.appendLine(`📂 Target files: ${targetFiles.length}`);

      const result = await smartModeSSEClient.connectReviewStream(
        targetFiles,
        '', // No diff content
        instruction,
        0.9 // High confidence for explicit user instruction
      );

      this.outputChannel.appendLine(`✅ Custom instruction completed: ${result.mode} mode`);

      return result;

    } catch (error) {
      this.outputChannel.appendLine(`❌ Custom instruction failed: ${error}`);
      vscode.window.showErrorMessage(`Smart Mode failed: ${error}`);
    }
  }

  /**
   * Apply Smart Diff - analyze existing diff content with Smart Mode
   */
  public async applySmartDiff(diffContent: string): Promise<SmartModeResult | undefined> {
    try {
      if (!diffContent || diffContent.trim().length === 0) {
        vscode.window.showWarningMessage('No diff content provided for Smart Mode analysis.');
        return;
      }

      this.outputChannel.appendLine('🔧 Applying Smart Diff with intelligent routing...');

      // Extract files from diff content
      const affectedFiles = this.extractFilesFromDiff(diffContent);

      const result = await smartModeSSEClient.connectReviewStream(
        affectedFiles,
        diffContent,
        'Apply the provided diff with smart risk analysis',
        0.8 // High confidence for explicit diff
      );

      this.outputChannel.appendLine(`✅ Smart Diff applied: ${result.mode} mode used`);

      return result;

    } catch (error) {
      this.outputChannel.appendLine(`❌ Smart Diff application failed: ${error}`);
      vscode.window.showErrorMessage(`Smart Diff failed: ${error}`);
    }
  }

  /**
   * Undo last Smart Mode operation
   */
  public async undoLastSmartMode(): Promise<void> {
    try {
      const success = await undoManager.undoLast();

      if (success) {
        vscode.window.showInformationMessage(
          `✅ Undone Smart Mode operation`,
          'View Changes'
        ).then(selection => {
          if (selection === 'View Changes') {
            vscode.commands.executeCommand('workbench.scm.focus');
          }
        });

        this.outputChannel.appendLine(`↩️ Undone Smart Mode operation`);
      } else {
        vscode.window.showWarningMessage('No Smart Mode operations to undo.');
      }

    } catch (error) {
      this.outputChannel.appendLine(`❌ Undo failed: ${error}`);
      vscode.window.showErrorMessage(`Undo failed: ${error}`);
    }
  }

  /**
   * Open Smart Mode settings
   */
  public async openSmartModeSettings(): Promise<void> {
    await vscode.commands.executeCommand('workbench.action.openSettings', 'aep.smartMode');
  }

  /**
   * Get all relevant files in the workspace for Smart Mode analysis
   */
  private async getWorkspaceFiles(): Promise<string[]> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      return [];
    }

    // Use VS Code's file search to find relevant files
    const files = await vscode.workspace.findFiles(
      '**/*.{ts,js,tsx,jsx,py,java,cpp,c,h,cs,go,rs,rb,php,swift,kt}', // Supported file types
      '**/node_modules/**', // Exclude patterns
      1000 // Max results
    );

    return files
      .map(uri => uri.fsPath)
      .filter(path => !path.includes('node_modules') && !path.includes('.git'));
  }

  /**
   * Let user select specific files for Smart Mode
   */
  private async selectTargetFiles(): Promise<string[]> {
    const workspaceFiles = await this.getWorkspaceFiles();

    if (workspaceFiles.length === 0) {
      return [];
    }

    const selectedFiles = await vscode.window.showQuickPick(
      workspaceFiles.map(file => ({
        label: vscode.workspace.asRelativePath(file),
        description: file,
        picked: false
      })),
      {
        canPickMany: true,
        placeHolder: 'Select files for Smart Mode analysis (use Cmd/Ctrl to multi-select)'
      }
    );

    return selectedFiles?.map(item => item.description) || [];
  }

  /**
   * Extract affected files from unified diff content
   */
  private extractFilesFromDiff(diffContent: string): string[] {
    const fileMatches = diffContent.match(/^\+\+\+ (.+)$/gm);

    if (!fileMatches) {
      return [];
    }

    return fileMatches
      .map(match => match.replace(/^\+\+\+ /, '').replace(/\t.*$/, ''))
      .filter(file => file !== '/dev/null')
      .map(file => file.startsWith('b/') ? file.substring(2) : file);
  }
}

// Export commands instance
export const smartModeCommands = new SmartModeCommands();