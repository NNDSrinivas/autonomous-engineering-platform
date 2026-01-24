/**
 * Autonomous Execution Module
 * 
 * Provides LLM action parsing and terminal capture capabilities
 * that integrate with existing ActionRegistry, FailureAnalyzer, and SelfHealingLoop.
 * 
 * Components:
 * - ActionMarkerParser: Parses [[ACTION:]] markers from LLM output
 * - TerminalOutputCapture: Captures terminal output with error detection
 * - AutonomousExecutionOrchestrator: Coordinates execution with autonomous retry
 * 
 * Usage:
 * ```typescript
 * const orchestrator = new AutonomousExecutionOrchestrator(
 *   actionRegistry,
 *   failureAnalyzer,
 *   selfHealingLoop
 * );
 * 
 * const result = await orchestrator.executePlan(llmOutput, {
 *   workspaceRoot: '/path/to/workspace',
 *   autoRetry: true,
 *   maxRetries: 3
 * });
 * ```
 */

export { ActionMarkerParser, ParsedAction, ParsedActionPlan } from './ActionMarkerParser';
export { TerminalOutputCapture, CommandResult, TerminalOutputEvent, OutputCallback } from './TerminalOutputCapture';
export { AutonomousExecutionOrchestrator, ExecutionOptions, ExecutionResult } from './AutonomousExecutionOrchestrator';
