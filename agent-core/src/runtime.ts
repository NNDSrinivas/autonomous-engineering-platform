import { coreApi } from './env';
import type { Greeting, Plan, PlanItem, PlanWithTelemetry } from './protocol';
import { generatePlan } from './router';
import { record } from './telemetry';

export async function greet(): Promise<Greeting> {
  const name = process.env.USER || 'Developer';
  const hr = new Date().getHours();
  const part = hr < 12 ? 'Morning' : hr < 18 ? 'Afternoon' : 'Evening';
  let tasks: any[] = [];
  try {
    const r = await fetch(`${coreApi()}/api/jira/tasks`);
    const j = await r.json();
    tasks = (j.items || []).slice(0, 5).map((t: any) => ({ key: t.key, title: t.summary, status: t.status }));
  } catch {}
  return { text: `Hello ${name}, Good ${part}! You have ${tasks.length} assigned tasks. Pick one to start:`, tasks };
}

export async function fetchContextPack(key: string): Promise<any> {
  try {
    const r = await fetch(`${coreApi()}/api/context/task/${encodeURIComponent(key)}`);
    return await r.json();
  } catch {
    return { ticket: { key }, explain: { what: "", why: "", how: [] }, sources: {} };
  }
}

export async function proposePlan(pack: any): Promise<Plan> {
  const files = ['backend/auth/jwt.py'];
  return {
    items: [
      { id: 'p1', kind: 'edit', desc: `Implement fix for ${pack?.ticket?.key || 'ticket'} (JWT expiry)`, files },
      { id: 'p2', kind: 'test', desc: 'Run focused tests', command: 'pytest -q tests/auth/test_jwt.py' },
      { id: 'p3', kind: 'cmd',  desc: 'Run full test suite', command: 'pytest -q' },
      { id: 'p4', kind: 'git',  desc: 'Create branch & commit', command: 'git checkout -b feat/jwt-expiry && git add -A && git commit -m "feat: jwt expiry fix (#ticket)"' }
    ]
  };
}

export async function proposePlanLLM(pack: any): Promise<PlanWithTelemetry> {
  try {
    const response = await generatePlan(pack);
    
    // Record telemetry data
    if (response.telemetry) {
      record(response.telemetry);
    }
    
    // Return plan with telemetry
    return { 
      ...response.plan, 
      telemetry: response.telemetry 
    };
  } catch (error) {
    console.error('LLM plan generation failed:', error);
    
    // Fallback to hardcoded plan on error
    return proposePlan(pack);
  }
}

// Enhanced chat functions for conversational interface
export async function generateChatWelcome(): Promise<{ text: string; suggestions: string[] }> {
  try {
    const name = process.env.USER || 'Developer';
    const hr = new Date().getHours();
    const timeOfDay = hr < 12 ? 'morning' : hr < 18 ? 'afternoon' : 'evening';
    
    // Get team context for welcome message
    let tasks: any[] = [];
    let teamActivity: any[] = [];
    
    try {
      const [tasksResponse, activityResponse] = await Promise.all([
        fetch(`${coreApi()}/api/jira/tasks`),
        fetch(`${coreApi()}/api/activity/recent`)
      ]);
      
      if (tasksResponse.ok) {
        const taskData = await tasksResponse.json();
        tasks = (taskData.items || []).slice(0, 3);
      }
      
      if (activityResponse.ok) {
        const activityData = await activityResponse.json();
        teamActivity = (activityData.items || []).slice(0, 2);
      }
    } catch (e) {
      // Continue with empty data if API calls fail
    }
    
    let text = `Good ${timeOfDay}, ${name}! 👋\n\n`;
    
    if (tasks.length > 0) {
      text += `You have ${tasks.length} active tasks:\n`;
      tasks.forEach((task, idx) => {
        text += `${idx + 1}. **${task.key}**: ${task.summary}\n`;
      });
      text += '\n';
    }
    
    if (teamActivity.length > 0) {
      text += `🔄 Recent team activity:\n`;
      teamActivity.forEach(activity => {
        text += `• ${activity.summary}\n`;
      });
      text += '\n';
    }
    
    text += `What would you like to work on today?`;
    
    const suggestions = [
      'Show me my highest priority task',
      'What are my teammates working on?',
      'Help me resolve merge conflicts',
      'Generate a plan for my next task',
      'Review recent changes and suggest improvements'
    ];
    
    return { text, suggestions };
  } catch (error) {
    const name = process.env.USER || 'Developer';
    return {
      text: `Hello ${name}! I'm your autonomous engineering assistant. How can I help you today?`,
      suggestions: ['Show me my tasks', 'Help me with current work', 'Generate a plan']
    };
  }
}

export async function handleChatMessage(message: string, context?: any): Promise<{ 
  content: string; 
  suggestions?: string[]; 
  context?: any 
}> {
  try {
    // Call the enhanced chat API
    const response = await fetch(`${coreApi()}/api/chat/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        conversationHistory: context?.history || [],
        currentTask: context?.currentTask,
        teamContext: context?.teamContext
      })
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    // Fallback to simple responses
    return generateSimpleChatResponse(message);
  }
}

function generateSimpleChatResponse(message: string): { 
  content: string; 
  suggestions: string[] 
} {
  const msg = message.toLowerCase();
  
  if (msg.includes('task') || msg.includes('jira')) {
    return {
      content: 'I can help you with your tasks! Let me fetch your current assignments.',
      suggestions: ['Show highest priority task', 'Create a plan for next task', 'Show task dependencies']
    };
  }
  
  if (msg.includes('team') || msg.includes('colleague')) {
    return {
      content: 'Let me show you what your team is working on and how it connects to your work.',
      suggestions: ['Show team activity', 'Find related work', 'Check for blockers']
    };
  }
  
  if (msg.includes('plan') || msg.includes('how')) {
    return {
      content: 'I can generate a detailed plan for your work. What specific task or goal would you like me to help with?',
      suggestions: ['Generate implementation plan', 'Break down complex task', 'Show dependencies']
    };
  }
  
  return {
    content: 'I\'m here to help with your engineering work! I can assist with tasks, team coordination, code planning, and more.',
    suggestions: ['Show my tasks', 'Generate a plan', 'Check team status', 'Help with current work']
  };
}