/**
 * Autonomous Execution Orchestrator
 * 
 * Integrates ActionMarkerParser, TerminalOutputCapture with existing:
 * - ActionRegistry
 * - FailureAnalyzer
 * - SelfHealingLoop
 * 
 * Provides unified autonomous execution without duplicating existing systems.
 */

import * as vscode from 'vscode';
import { ActionRegistry, ActionContext, ActionResult } from '../../actions/ActionRegistry';
import { ActionMarkerParser, ParsedActionPlan } from './ActionMarkerParser';
import { TerminalOutputCapture, CommandResult } from './TerminalOutputCapture';
import { FailureAnalyzer } from '../validation/FailureAnalyzer';
import { SelfHealingLoop } from '../validation/SelfHealingLoop';

export interface ExecutionOptions {
  workspaceRoot: string;
  autoRetry?: boolean;
  maxRetries?: number;
  approvedViaChat?: boolean;
  onProgress?: (message: string) => void;
}

export interface ExecutionResult {
  success: boolean;
  actionsExecuted: number;
  actionsFailed: number;
  commandResults: CommandResult[];
  healingAttempts?: number;
  errors: string[];
  message?: string;
}

/**
 * Orchestrates autonomous execution by coordinating existing systems
 */
export class AutonomousExecutionOrchestrator {
  private actionRegistry: ActionRegistry;
  private actionParser: ActionMarkerParser;
  private terminalCapture: TerminalOutputCapture;
  private failureAnalyzer?: FailureAnalyzer;
  private selfHealingLoop?: SelfHealingLoop;
  
  constructor(
    actionRegistry: ActionRegistry,
    failureAnalyzer?: FailureAnalyzer,
    selfHealingLoop?: SelfHealingLoop
  ) {
    this.actionRegistry = actionRegistry;
    this.actionParser = new ActionMarkerParser();
    this.terminalCapture = new TerminalOutputCapture();
    this.failureAnalyzer = failureAnalyzer;
    this.selfHealingLoop = selfHealingLoop;
  }
  
  /**
   * Execute LLM-generated action plan with autonomous error handling
   */
  async executePlan(
    llmOutput: string,
    options: ExecutionOptions
  ): Promise<ExecutionResult> {
    const { onProgress } = options;
    
    onProgress?.('Parsing action markers from LLM output...');
    
    // Parse action markers
    const parsed = this.actionParser.parse(llmOutput);
    
    if (parsed.errors.length > 0) {
      return {
        success: false,
        actionsExecuted: 0,
        actionsFailed: 0,
        commandResults: [],
        errors: parsed.errors,
        message: 'Failed to parse action markers',
      };
    }
    
    onProgress?.(`Found ${parsed.actions.length} actions to execute`);
    
    // Convert to ActionRegistry format
    const actions = this.actionParser.toActionRegistryFormat(parsed);
    
    // Execute actions
    return this.executeActions(actions, options);
  }
  
  /**
   * Execute actions using ActionRegistry with autonomous retry
   */
  private async executeActions(
    actions: any[],
    options: ExecutionOptions
  ): Promise<ExecutionResult> {
    const { workspaceRoot, autoRetry = true, maxRetries = 3, approvedViaChat, onProgress } = options;
    
    const context: ActionContext = {
      workspaceRoot,
      approvedViaChat,
      showMessage: (msg: string) => onProgress?.(msg),
    };
    
    let actionsExecuted = 0;
    let actionsFailed = 0;
    const commandResults: CommandResult[] = [];
    const errors: string[] = [];
    let healingAttempts = 0;
    
    for (let i = 0; i < actions.length; i++) {
      const action = actions[i];
      onProgress?.(`Executing action ${i + 1}/${actions.length}: ${action.type}`);
      
      let result: ActionResult;
      let retries = 0;
      
      do {
        // Execute action through ActionRegistry
        if (action.type === 'runCommand') {
          // Use terminal capture for commands
          const cmdResult = await this.executeCommandWithCapture(
            action.command,
            workspaceRoot,
            onProgress
          );
          commandResults.push(cmdResult);
          
          result = {
            success: cmdResult.success,
            message: cmdResult.success ? 'Command executed' : 'Command failed',
            error: cmdResult.success ? undefined : new Error(cmdResult.errors.join('\n')),
          };
        } else {
          // Use ActionRegistry for file operations
          result = await this.actionRegistry.execute(action, context);
        }
        
        // If failed and auto-retry enabled, try to heal
        if (!result.success && autoRetry && retries < maxRetries) {
          onProgress?.(`Action failed, attempting autonomous healing (${retries + 1}/${maxRetries})...`);
          
          // Use existing FailureAnalyzer and SelfHealingLoop if available
          if (this.failureAnalyzer && this.selfHealingLoop && result.error) {
            healingAttempts++;
            
            // Analyze failure
            const analysis = await this.analyzeFailure(result.error, action);
            
            // Attempt healing
            const healed = await this.attemptHealing(analysis, action, context);
            
            if (healed.success) {
              onProgress?.('Autonomous healing successful!');
              result = healed;
              break;
            }
          }
          
          retries++;
        } else {
          break;
        }
      } while (!result.success && retries < maxRetries);
      
      if (result.success) {
        actionsExecuted++;
      } else {
        actionsFailed++;
        errors.push(result.error?.message || 'Unknown error');
      }
      
      // Stop on first failure if auto-retry disabled
      if (!result.success && !autoRetry) {
        break;
      }
    }
    
    return {
      success: actionsFailed === 0,
      actionsExecuted,
      actionsFailed,
      commandResults,
      healingAttempts: healingAttempts > 0 ? healingAttempts : undefined,
      errors,
      message: actionsFailed === 0
        ? `Successfully executed ${actionsExecuted} actions`
        : `Executed ${actionsExecuted} actions, ${actionsFailed} failed`,
    };
  }
  
  /**
   * Execute command with terminal output capture
   */
  private async executeCommandWithCapture(
    command: string,
    cwd: string,
    onProgress?: (msg: string) => void
  ): Promise<CommandResult> {
    return this.terminalCapture.executeCommand(command, {
      cwd,
      onOutput: (event) => {
        if (event.type === 'stderr' || event.type === 'error') {
          onProgress?.(`⚠️ ${event.content}`);
        }
      },
    });
  }
  
  /**
   * Analyze failure using existing FailureAnalyzer
   */
  private async analyzeFailure(error: Error, action: any): Promise<any> {
    // This would integrate with existing FailureAnalyzer
    // For now, return basic analysis
    return {
      error: error.message,
      action,
      severity: 'high',
    };
  }
  
  /**
   * Attempt healing using existing SelfHealingLoop
   */
  private async attemptHealing(
    analysis: any,
    action: any,
    context: ActionContext
  ): Promise<ActionResult> {
    // This would integrate with existing SelfHealingLoop
    // For now, return failure (actual implementation would use SelfHealingLoop)
    return {
      success: false,
      error: new Error('Healing not implemented'),
    };
  }
}
