// extensions/vscode-aep/src/decorations/reviewDecorations.ts
/**
 * Review Decorations System
 * 
 * Provides visual indicators in the editor for Navi code review issues:
 * - Squiggly lines under problematic code
 * - Hover tooltips with AI explanations
 * - Color-coded severity indicators
 * - Overview ruler markers
 * 
 * Part of Batch 7 — Advanced Intelligence Layer
 */

import * as vscode from 'vscode';

interface ReviewIssue {
  file: string;
  line: number;
  column?: number;
  length?: number;
  message: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  source: 'navi';
  fixId?: string;
  confidence?: number;
  riskLevel?: 'low' | 'medium' | 'high' | 'critical';
}

export class ReviewDecorations {
  private diagnosticCollection: vscode.DiagnosticCollection;
  
  // Decoration types for different severity levels
  private readonly decorationTypes = {
    info: vscode.window.createTextEditorDecorationType({
      borderWidth: '1px',
      borderStyle: 'dotted',
      borderColor: new vscode.ThemeColor('editorInfo.foreground'),
      backgroundColor: new vscode.ThemeColor('editorInfo.background'),
      overviewRulerColor: new vscode.ThemeColor('editorInfo.foreground'),
      overviewRulerLane: vscode.OverviewRulerLane.Right,
      rangeBehavior: vscode.DecorationRangeBehavior.ClosedClosed,
    }),
    
    warning: vscode.window.createTextEditorDecorationType({
      borderWidth: '1px',
      borderStyle: 'solid',
      borderColor: new vscode.ThemeColor('editorWarning.foreground'),
      backgroundColor: new vscode.ThemeColor('editorWarning.background'),
      overviewRulerColor: new vscode.ThemeColor('editorWarning.foreground'),
      overviewRulerLane: vscode.OverviewRulerLane.Right,
      rangeBehavior: vscode.DecorationRangeBehavior.ClosedClosed,
    }),
    
    error: vscode.window.createTextEditorDecorationType({
      borderWidth: '2px',
      borderStyle: 'solid',
      borderColor: new vscode.ThemeColor('editorError.foreground'),
      backgroundColor: new vscode.ThemeColor('editorError.background'),
      overviewRulerColor: new vscode.ThemeColor('editorError.foreground'),
      overviewRulerLane: vscode.OverviewRulerLane.Right,
      rangeBehavior: vscode.DecorationRangeBehavior.ClosedClosed,
    }),
    
    critical: vscode.window.createTextEditorDecorationType({
      borderWidth: '3px',
      borderStyle: 'solid',
      borderColor: '#dc2626',
      backgroundColor: 'rgba(220, 38, 38, 0.1)',
      overviewRulerColor: '#dc2626',
      overviewRulerLane: vscode.OverviewRulerLane.Right,
      rangeBehavior: vscode.DecorationRangeBehavior.ClosedClosed,
      after: {
        contentText: ' ⚠️',
        color: '#dc2626',
      }
    }),
  };

  constructor(context: vscode.ExtensionContext) {
    // Create diagnostic collection for Navi issues
    this.diagnosticCollection = vscode.languages.createDiagnosticCollection('navi');
    context.subscriptions.push(this.diagnosticCollection);
    
    // Register hover provider
    context.subscriptions.push(
      vscode.languages.registerHoverProvider('*', this.createHoverProvider())
    );
    
    // Clean up decorations on dispose
    context.subscriptions.push(new vscode.Disposable(() => {
      Object.values(this.decorationTypes).forEach(type => type.dispose());
    }));
  }

  /**
   * Apply decorations to editor for review issues
   */
  public applyDecorations(issues: ReviewIssue[]): void {
    // Group issues by file and severity
    const issuesByFile = new Map<string, ReviewIssue[]>();
    const decorationsByEditor = new Map<vscode.TextEditor, Map<string, vscode.DecorationOptions[]>>();

    // Group issues by file
    issues.forEach(issue => {
      const fileIssues = issuesByFile.get(issue.file) || [];
      fileIssues.push(issue);
      issuesByFile.set(issue.file, fileIssues);
    });

    // Apply diagnostics (for Problems panel and quick fixes)
    this.applyDiagnostics(issuesByFile);

    // Apply visual decorations to open editors
    vscode.window.visibleTextEditors.forEach(editor => {
      const filePath = editor.document.uri.fsPath;
      const fileIssues = issuesByFile.get(filePath);
      
      if (fileIssues && fileIssues.length > 0) {
        const decorationMap = this.createDecorationMap(fileIssues, editor);
        decorationsByEditor.set(editor, decorationMap);
        
        // Apply decorations by severity
        Object.entries(this.decorationTypes).forEach(([severity, decorationType]) => {
          const decorations = decorationMap.get(severity) || [];
          editor.setDecorations(decorationType, decorations);
        });
      }
    });
  }

  /**
   * Clear all decorations
   */
  public clearDecorations(): void {
    this.diagnosticCollection.clear();
    
    vscode.window.visibleTextEditors.forEach(editor => {
      Object.values(this.decorationTypes).forEach(decorationType => {
        editor.setDecorations(decorationType, []);
      });
    });
  }

  /**
   * Apply diagnostics for VS Code Problems panel integration
   */
  private applyDiagnostics(issuesByFile: Map<string, ReviewIssue[]>): void {
    issuesByFile.forEach((issues, filePath) => {
      const diagnostics: vscode.Diagnostic[] = issues.map(issue => {
        const range = this.createRange(issue);
        const diagnostic = new vscode.Diagnostic(range, issue.message, this.getSeverity(issue.severity));
        
        diagnostic.source = 'navi';
        diagnostic.code = issue.fixId || 'navi-issue';
        
        // Add additional metadata
        if (issue.confidence) {
          diagnostic.tags = [
            issue.confidence < 0.7 ? vscode.DiagnosticTag.Unnecessary : undefined
          ].filter(Boolean) as vscode.DiagnosticTag[];
        }
        
        return diagnostic;
      });
      
      const uri = vscode.Uri.file(filePath);
      this.diagnosticCollection.set(uri, diagnostics);
    });
  }

  /**
   * Create decoration map organized by severity
   */
  private createDecorationMap(issues: ReviewIssue[], editor: vscode.TextEditor): Map<string, vscode.DecorationOptions[]> {
    const decorationMap = new Map<string, vscode.DecorationOptions[]>();
    
    // Initialize maps for each severity level
    Object.keys(this.decorationTypes).forEach(severity => {
      decorationMap.set(severity, []);
    });

    issues.forEach(issue => {
      const range = this.createRange(issue);
      const decoration: vscode.DecorationOptions = {
        range,
        hoverMessage: this.createHoverMessage(issue),
      };
      
      const severityDecorations = decorationMap.get(issue.severity) || [];
      severityDecorations.push(decoration);
      decorationMap.set(issue.severity, severityDecorations);
    });

    return decorationMap;
  }

  /**
   * Create range from issue location data
   */
  private createRange(issue: ReviewIssue): vscode.Range {
    const line = Math.max(0, (issue.line || 1) - 1); // Convert to 0-based
    const column = Math.max(0, (issue.column || 1) - 1);
    const length = issue.length || 1;
    
    return new vscode.Range(
      new vscode.Position(line, column),
      new vscode.Position(line, column + length)
    );
  }

  /**
   * Convert severity to VS Code diagnostic severity
   */
  private getSeverity(severity: string): vscode.DiagnosticSeverity {
    switch (severity) {
      case 'error':
      case 'critical':
        return vscode.DiagnosticSeverity.Error;
      case 'warning':
        return vscode.DiagnosticSeverity.Warning;
      case 'info':
      default:
        return vscode.DiagnosticSeverity.Information;
    }
  }

  /**
   * Create hover message with rich formatting
   */
  private createHoverMessage(issue: ReviewIssue): vscode.MarkdownString {
    const markdown = new vscode.MarkdownString();
    markdown.isTrusted = true;
    
    // Main message
    markdown.appendMarkdown(`**🤖 Navi Analysis**\n\n`);
    markdown.appendMarkdown(`${issue.message}\n\n`);
    
    // Severity and confidence
    const severityIcon = this.getSeverityIcon(issue.severity);
    markdown.appendMarkdown(`${severityIcon} **Severity:** ${issue.severity.toUpperCase()}\n\n`);
    
    if (issue.confidence) {
      const confidencePercentage = Math.round(issue.confidence * 100);
      markdown.appendMarkdown(`📊 **Confidence:** ${confidencePercentage}%\n\n`);
    }
    
    if (issue.riskLevel) {
      markdown.appendMarkdown(`⚠️ **Risk Level:** ${issue.riskLevel}\n\n`);
    }
    
    // Actions
    if (issue.fixId) {
      markdown.appendMarkdown(`---\n\n`);
      markdown.appendMarkdown(`[🔧 Apply Auto-Fix](command:aep.applyNaviFix?${encodeURIComponent(JSON.stringify({ fixId: issue.fixId }))})\n\n`);
      markdown.appendMarkdown(`[📋 Explain Issue](command:aep.explainIssue?${encodeURIComponent(JSON.stringify({ issue: issue.message }))})\n\n`);
    }
    
    return markdown;
  }

  /**
   * Get emoji icon for severity level
   */
  private getSeverityIcon(severity: string): string {
    switch (severity) {
      case 'critical': return '🔥';
      case 'error': return '❌';
      case 'warning': return '⚠️';
      case 'info': return 'ℹ️';
      default: return '📝';
    }
  }

  /**
   * Create hover provider for additional context
   */
  private createHoverProvider(): vscode.HoverProvider {
    return {
      provideHover: (document, position) => {
        // Check if there's a diagnostic at this position
        const diagnostics = this.diagnosticCollection.get(document.uri);
        if (!diagnostics) return;

        const hoveredDiagnostic = diagnostics.find(diagnostic => 
          diagnostic.range.contains(position)
        );

        if (hoveredDiagnostic && hoveredDiagnostic.source === 'navi') {
          const markdown = new vscode.MarkdownString();
          markdown.appendMarkdown(`**🤖 Navi:** ${hoveredDiagnostic.message}`);
          return new vscode.Hover(markdown);
        }
      }
    };
  }
}

// Export interface for external use
export type { ReviewIssue };