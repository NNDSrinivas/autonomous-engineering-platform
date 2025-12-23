import { Dispatch } from "react";
import { UIAction, TodoItem } from "./uiStore";

/**
 * Agent Workflow Orchestrator - Simulates Copilot-style temporal experience
 * 
 * Phase 4.0: Instead of dumping final text, orchestrates UI events over time:
 * thinking → steps → commands → results → proposals
 * 
 * This creates the "alive" feeling that separates Copilot from basic chat.
 */

export class AgentWorkflowOrchestrator {
  private dispatch: Dispatch<UIAction>;
  private delays = {
    thinking: 800,
    step: 1200,
    command: 600,
    result: 400
  };

  constructor(dispatch: Dispatch<UIAction>) {
    this.dispatch = dispatch;
  }

  /**
   * Simulate agent responding to "Is backend up and running?"
   * Shows the full Copilot-style workflow instead of instant text dump
   */
  async simulateBackendCheckWorkflow(userMessage: string) {
    console.log('🤖 Starting Agent workflow simulation...');
    
    // 1. Start agent workflow
    this.dispatch({ type: 'AGENT_START' });
    
    // 2. Show thinking
    this.dispatch({ 
      type: 'ADD_ASSISTANT_MESSAGE', 
      content: 'Thinking...',
      messageType: 'thinking'
    });
    
    await this.delay(this.delays.thinking);
    
    // 3. Add todos and start executing
    const todos: TodoItem[] = [
      { id: '1', text: 'Check running tasks', status: 'active' },
      { id: '2', text: 'Test health endpoint', status: 'pending' },
      { id: '3', text: 'Verify API connectivity', status: 'pending' }
    ];
    
    for (const todo of todos) {
      this.dispatch({ type: 'AGENT_ADD_TODO', todo });
    }
    
    // 4. Execute steps with live updates
    this.dispatch({ 
      type: 'ADD_ASSISTANT_MESSAGE', 
      content: 'Checking running tasks...',
      messageType: 'step'
    });
    
    await this.delay(this.delays.step);
    
    // Complete first todo
    this.dispatch({ type: 'AGENT_UPDATE_TODO', id: '1', status: 'completed' });
    this.dispatch({ type: 'AGENT_UPDATE_TODO', id: '2', status: 'active' });
    
    this.dispatch({ 
      type: 'ADD_ASSISTANT_MESSAGE', 
      content: '✅ Found backend:start (uvicorn) task running',
      messageType: 'result'
    });
    
    await this.delay(this.delays.result);
    
    // 5. Next step
    this.dispatch({ 
      type: 'ADD_ASSISTANT_MESSAGE', 
      content: 'Testing health endpoint...',
      messageType: 'step'
    });
    
    await this.delay(this.delays.step);
    
    // Complete second todo  
    this.dispatch({ type: 'AGENT_UPDATE_TODO', id: '2', status: 'completed' });
    this.dispatch({ type: 'AGENT_UPDATE_TODO', id: '3', status: 'active' });
    
    // 6. Show command that will be executed
    this.dispatch({ 
      type: 'ADD_ASSISTANT_MESSAGE', 
      content: 'curl -s http://127.0.0.1:8787/health',
      messageType: 'command'
    });
    
    await this.delay(this.delays.command);
    
    this.dispatch({ 
      type: 'ADD_ASSISTANT_MESSAGE', 
      content: '✅ Backend is healthy: {"status":"ok","service":"core"}',
      messageType: 'result'
    });
    
    // Complete final todo
    this.dispatch({ type: 'AGENT_UPDATE_TODO', id: '3', status: 'completed' });
    
    await this.delay(this.delays.result);
    
    // 7. Summary and proposal
    this.dispatch({ 
      type: 'ADD_ASSISTANT_MESSAGE', 
      content: 'Your backend is up and running correctly on port 8787. All health checks passed.',
      messageType: 'text'
    });
    
    await this.delay(500);
    
    this.dispatch({ 
      type: 'ADD_ASSISTANT_MESSAGE', 
      content: 'Would you like me to connect the chat interface to the backend API so you can have real conversations?',
      messageType: 'proposal'
    });
    
    // 8. Stop workflow
    this.dispatch({ type: 'AGENT_STOP' });
    
    console.log('✅ Agent workflow simulation complete');
  }
  
  /**
   * Generic agent workflow for any user message
   * Adapts the steps based on the message content
   */
  async simulateAgentResponse(userMessage: string, mode: string, model: string) {
    const lowerMessage = userMessage.toLowerCase();
    
    if (lowerMessage.includes('backend') || lowerMessage.includes('health') || lowerMessage.includes('running')) {
      return this.simulateBackendCheckWorkflow(userMessage);
    }
    
    // Default workflow for other messages
    this.dispatch({ type: 'AGENT_START' });
    
    this.dispatch({ 
      type: 'ADD_ASSISTANT_MESSAGE', 
      content: 'Thinking...',
      messageType: 'thinking'
    });
    
    await this.delay(this.delays.thinking);
    
    // Add a simple todo
    this.dispatch({ 
      type: 'AGENT_ADD_TODO', 
      todo: { id: '1', text: `Process: ${userMessage}`, status: 'active' }
    });
    
    await this.delay(this.delays.step);
    
    this.dispatch({ type: 'AGENT_UPDATE_TODO', id: '1', status: 'completed' });
    
    this.dispatch({ 
      type: 'ADD_ASSISTANT_MESSAGE', 
      content: `I understand you said "${userMessage}". I'm ready to help with code-related tasks.`,
      messageType: 'text'
    });
    
    this.dispatch({ 
      type: 'ADD_ASSISTANT_MESSAGE', 
      content: 'What would you like me to help you with next?',
      messageType: 'proposal'
    });
    
    this.dispatch({ type: 'AGENT_STOP' });
  }
  
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}