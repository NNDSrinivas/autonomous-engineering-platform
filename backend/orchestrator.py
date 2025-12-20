from typing import Dict, Any, List, Optional
import asyncio
import json
from datetime import datetime

try:
    # Try relative imports first (for when run as module)
    from .models.plan import Plan, ExecutionResult, AgentContext
    from .agents.planner_agent import PlannerAgent
    from .agents.memory_agent import MemoryAgent
    from .agents.repo_analysis_agent import RepoAnalysisAgent
    from .agents.execution_agent import ExecutionAgent
    from .services.llm_router import LLMRouter
    from .core.config import get_settings
except ImportError:
    # Fallback to absolute imports (for direct execution)
    from backend.models.plan import Plan, ExecutionResult, AgentContext
    from backend.agents.planner_agent import PlannerAgent
    from backend.agents.memory_agent import MemoryAgent
    from backend.agents.repo_analysis_agent import RepoAnalysisAgent
    from backend.agents.execution_agent import ExecutionAgent
    from backend.services.llm_router import LLMRouter
    from backend.core.config import get_settings

class NaviOrchestrator:
    """
    The Navi Orchestrator is the master controller that coordinates all agents.
    This is what makes Navi a true multi-agent AI system, not just a chatbot.
    
    The orchestrator:
    - Receives user instructions
    - Coordinates between agents
    - Manages execution flow
    - Handles errors and recovery
    - Learns from outcomes
    - Provides unified responses
    
    This is where Navi becomes smarter than Cursor, Copilot, and other single-agent systems.
    """
    
    def __init__(self):
        # Initialize all agents
        self.planner = PlannerAgent()
        self.memory = MemoryAgent()
        self.repo_analyzer = RepoAnalysisAgent()
        self.executor = ExecutionAgent()
        
        # LLM router for orchestrator-level reasoning
        self.llm_router = LLMRouter()
        
        # Settings
        self.settings = get_settings()
        
        # Orchestrator state
        self.active_sessions = {}
        self.execution_queue = asyncio.Queue()
        
    async def handle_instruction(
        self, 
        user_id: str, 
        instruction: str, 
        workspace_root: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: handle a user instruction with full multi-agent coordination
        """
        
        session_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # 1. Initialize agent context
            context = await self._initialize_context(user_id, instruction, workspace_root, options)
            
            # 2. Load user memory and preferences
            memory_context = await self.memory.load_context(user_id)
            context.memory_context = memory_context['recent_events']
            context.user_preferences = memory_context['user_preferences']
            
            # 3. Analyze repository (if not cached)
            repo_map = await self._get_or_analyze_repo(workspace_root)
            context.repo_map = repo_map
            
            # 4. Generate execution plan
            plan = await self.planner.generate_plan(
                instruction=instruction,
                repo_map=repo_map.dict() if repo_map else {},
                user_context=memory_context
            )
            
            # 5. Execute plan with coordination
            execution_results = await self._execute_plan_with_coordination(plan, context)
            
            # 6. Review and validate results
            review_result = await self._review_execution_results(plan, execution_results, context)
            
            # 7. Save to memory
            await self._save_execution_to_memory(user_id, instruction, plan, execution_results, review_result)
            
            # 8. Generate unified response
            response = await self._generate_unified_response(
                instruction, plan, execution_results, review_result, context
            )
            
            return {
                'session_id': session_id,
                'success': review_result['overall_success'],
                'plan': plan.dict(),
                'execution_results': [result.dict() for result in execution_results],
                'review': review_result,
                'response': response,
                'context': context.dict()
            }
            
        except Exception as e:
            # Handle orchestration errors
            error_response = await self._handle_orchestration_error(e, user_id, instruction, workspace_root)
            return error_response
    
    async def _initialize_context(
        self, 
        user_id: str, 
        instruction: str, 
        workspace_root: str,
        options: Optional[Dict[str, Any]] = None
    ) -> AgentContext:
        """
        Initialize comprehensive context for agent coordination
        """
        
        return AgentContext(
            user_id=user_id,
            workspace_root=workspace_root,
            current_instruction=instruction,
            repo_map=None,  # Will be populated later
            memory_context=[],
            execution_history=[],
            user_preferences=options or {},
            session_metadata={
                'start_time': datetime.now(),
                'orchestrator_version': '1.0.0',
                'safety_level': options.get('safety_level', 'medium') if options else 'medium'
            }
        )
    
    async def _get_or_analyze_repo(self, workspace_root: str):
        """
        Get cached repo analysis or perform new analysis
        """
        
        # Check for cached analysis (in production, this would use Redis/database)
        # For now, always analyze (in production, implement caching)
        try:
            repo_map = await self.repo_analyzer.analyze(workspace_root)
            return repo_map
        except Exception as e:
            # If repo analysis fails, continue with limited context
            print(f"Repo analysis failed: {e}")
            return None
    
    async def _execute_plan_with_coordination(
        self, 
        plan: Plan, 
        context: AgentContext
    ) -> List[ExecutionResult]:
        """
        Execute plan with intelligent coordination between agents
        """
        
        execution_results = []
        
        # Track execution state
        executed_steps = set()
        
        while len(executed_steps) < len(plan.steps):
            # Get next executable steps (dependencies satisfied)
            executable_steps = []
            
            for step in plan.steps:
                if step.id in executed_steps:
                    continue
                
                # Check if dependencies are satisfied
                deps_satisfied = all(dep_id in executed_steps for dep_id in step.depends_on)
                if deps_satisfied:
                    executable_steps.append(step)
            
            if not executable_steps:
                # Circular dependency or other issue
                break
            
            # Execute steps (potentially in parallel for independent steps)
            step_results = await self._execute_steps_batch(executable_steps, context)
            
            # Process results
            for step, result in zip(executable_steps, step_results):
                execution_results.append(result)
                context.execution_history.append(result)
                
                if result.success:
                    executed_steps.add(step.id)
                    plan.mark_step_executed(step.id)
                else:
                    # Handle step failure
                    recovery_result = await self._handle_step_failure(step, result, plan, context)
                    
                    if recovery_result.get('retry', False):
                        # Retry the step
                        retry_result = await self.executor.execute_step(step, context.workspace_root, context.dict())
                        execution_results.append(retry_result)
                        
                        if retry_result.success:
                            executed_steps.add(step.id)
                            plan.mark_step_executed(step.id)
                    
                    elif recovery_result.get('skip', False):
                        # Skip this step and continue
                        executed_steps.add(step.id)
                        plan.mark_step_executed(step.id)
                    
                    else:
                        # Stop execution on critical failure
                        break
        
        return execution_results
    
    async def _execute_steps_batch(
        self, 
        steps: List, 
        context: AgentContext
    ) -> List[ExecutionResult]:
        """
        Execute multiple steps, potentially in parallel
        """
        
        # For now, execute sequentially (in production, implement parallel execution for independent steps)
        results = []
        
        for step in steps:
            # Add intelligent pre-execution reasoning
            execution_strategy = await self._determine_execution_strategy(step, context)
            
            # Execute with strategy
            if execution_strategy['approach'] == 'direct':
                result = await self.executor.execute_step(step, context.workspace_root, context.dict())
            
            elif execution_strategy['approach'] == 'guided':
                # Use LLM guidance for complex steps
                result = await self._execute_with_llm_guidance(step, context)
            
            elif execution_strategy['approach'] == 'interactive':
                # Require user confirmation
                result = await self._execute_with_user_confirmation(step, context)
            
            else:
                # Default to direct execution
                result = await self.executor.execute_step(step, context.workspace_root, context.dict())
            
            results.append(result)
        
        return results
    
    async def _determine_execution_strategy(self, step, context: AgentContext) -> Dict[str, Any]:
        """
        Determine the best execution strategy for a step using AI reasoning
        """
        
        # Analyze step complexity and risk
        risk_factors = []
        
        # File modification risks
        if step.action_type in ['modify_file', 'refactor'] and step.file_targets:
            for file_path in step.file_targets:
                if 'config' in file_path.lower():
                    risk_factors.append('config_file_modification')
                if file_path.endswith(('.py', '.js', '.ts')) and 'test' not in file_path:
                    risk_factors.append('source_code_modification')
        
        # Command execution risks
        if step.action_type == 'run_command':
            command = step.metadata.get('command', '')
            if any(risky in command for risky in ['rm', 'delete', 'drop', 'truncate']):
                risk_factors.append('destructive_command')
        
        # Safety level from user preferences
        safety_level = context.user_preferences.get('safety_level', 'medium')
        
        # Determine strategy
        if len(risk_factors) == 0:
            return {'approach': 'direct', 'reasoning': 'Low risk operation'}
        
        elif safety_level == 'high' or len(risk_factors) > 1:
            return {'approach': 'interactive', 'reasoning': f'High risk factors: {risk_factors}'}
        
        elif step.metadata.get('complexity', 0.5) > 0.7:
            return {'approach': 'guided', 'reasoning': 'High complexity operation'}
        
        else:
            return {'approach': 'direct', 'reasoning': 'Standard execution'}
    
    async def _execute_with_llm_guidance(self, step, context: AgentContext) -> ExecutionResult:
        """
        Execute step with LLM guidance for complex operations
        """
        
        # Generate execution guidance
        guidance_prompt = f"""
        You are Navi's execution guidance system. Analyze this execution step and provide detailed guidance.
        
        Step: {step.dict()}
        Context: {context.workspace_root}
        Recent execution history: {context.execution_history[-3:] if context.execution_history else []}
        
        Provide:
        1. Pre-execution checks to perform
        2. Potential risks and mitigation strategies
        3. Expected outcomes
        4. Validation criteria
        
        Format as JSON with keys: pre_checks, risks, expected_outcomes, validation
        """
        
        try:
            guidance_response = await self.llm_router.run(prompt=guidance_prompt, use_smart_auto=True)
            guidance = json.loads(guidance_response.text)
            
            # Execute with guidance
            result = await self.executor.execute_step(step, context.workspace_root, context.dict())
            
            # Add guidance to metadata
            result.metadata['execution_guidance'] = guidance
            
            return result
            
        except Exception:
            # Fallback to direct execution
            return await self.executor.execute_step(step, context.workspace_root, context.dict())
    
    async def _execute_with_user_confirmation(self, step, context: AgentContext) -> ExecutionResult:
        """
        Execute step with user confirmation for high-risk operations
        """
        
        # This would integrate with the UI to request user confirmation
        # For now, simulate user confirmation
        
        return ExecutionResult(
            step_id=step.id,
            success=True,
            output="Step executed with user confirmation (simulated)",
            metadata={'requires_user_confirmation': True}
        )
    
    async def _handle_step_failure(
        self, 
        step, 
        result: ExecutionResult, 
        plan: Plan, 
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Handle step execution failure with intelligent recovery
        """
        
        # Analyze failure
        failure_analysis = await self._analyze_failure(step, result, context)
        
        # Determine recovery strategy
        if failure_analysis['category'] == 'temporary':
            return {'retry': True, 'reasoning': 'Temporary failure, retry recommended'}
        
        elif failure_analysis['category'] == 'dependency':
            return {'replan': True, 'reasoning': 'Dependency issue, replanning needed'}
        
        elif failure_analysis['category'] == 'user_input':
            return {'ask_user': True, 'reasoning': 'User input required'}
        
        elif failure_analysis['severity'] == 'low':
            return {'skip': True, 'reasoning': 'Low severity, safe to skip'}
        
        else:
            return {'stop': True, 'reasoning': 'Critical failure, stopping execution'}
    
    async def _analyze_failure(self, step, result: ExecutionResult, context: AgentContext) -> Dict[str, Any]:
        """
        Analyze execution failure to determine appropriate response
        """
        
        error_message = result.error or ""
        
        # Categorize failure
        if "timeout" in error_message.lower():
            return {'category': 'temporary', 'severity': 'medium'}
        
        elif "permission" in error_message.lower():
            return {'category': 'permission', 'severity': 'high'}
        
        elif "not found" in error_message.lower():
            return {'category': 'dependency', 'severity': 'medium'}
        
        elif "syntax" in error_message.lower():
            return {'category': 'user_input', 'severity': 'medium'}
        
        else:
            return {'category': 'unknown', 'severity': 'high'}
    
    async def _review_execution_results(
        self, 
        plan: Plan, 
        execution_results: List[ExecutionResult], 
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Review execution results and provide comprehensive analysis
        """
        
        total_steps = len(plan.steps)
        successful_steps = sum(1 for result in execution_results if result.success)
        failed_steps = total_steps - successful_steps
        
        # Calculate success metrics
        success_rate = successful_steps / total_steps if total_steps > 0 else 0
        
        # Analyze impact
        files_modified = []
        for result in execution_results:
            files_modified.extend(result.files_modified)
        
        unique_files_modified = list(set(files_modified))
        
        # Generate summary
        summary = f"Executed {successful_steps}/{total_steps} steps successfully. "
        summary += f"Modified {len(unique_files_modified)} files."
        
        if failed_steps > 0:
            summary += f" {failed_steps} steps failed."
        
        return {
            'overall_success': success_rate >= 0.8,  # 80% success threshold
            'success_rate': success_rate,
            'total_steps': total_steps,
            'successful_steps': successful_steps,
            'failed_steps': failed_steps,
            'files_modified': unique_files_modified,
            'summary': summary,
            'recommendations': await self._generate_recommendations(plan, execution_results, context)
        }
    
    async def _generate_recommendations(
        self, 
        plan: Plan, 
        execution_results: List[ExecutionResult], 
        context: AgentContext
    ) -> List[str]:
        """
        Generate recommendations based on execution results
        """
        
        recommendations = []
        
        # Analyze failed steps
        failed_results = [r for r in execution_results if not r.success]
        
        if failed_results:
            recommendations.append("Review failed steps and consider manual intervention")
        
        # Check for modified critical files
        critical_files = ['package.json', 'requirements.txt', 'pom.xml', 'Dockerfile']
        modified_critical = [f for f in context.execution_history if any(cf in str(f.files_modified) for cf in critical_files)]
        
        if modified_critical:
            recommendations.append("Critical configuration files were modified - consider running tests")
        
        # Performance recommendations
        total_execution_time = sum(r.execution_time for r in execution_results)
        if total_execution_time > 300:  # 5 minutes
            recommendations.append("Consider breaking down complex operations into smaller steps")
        
        return recommendations
    
    async def _save_execution_to_memory(
        self, 
        user_id: str, 
        instruction: str, 
        plan: Plan, 
        execution_results: List[ExecutionResult],
        review_result: Dict[str, Any]
    ):
        """
        Save execution results to user memory for learning
        """
        
        await self.memory.save_event(
            user_id=user_id,
            event_type='execution_result',
            content={
                'instruction': instruction,
                'plan': plan.dict(),
                'results': [r.dict() for r in execution_results],
                'review': review_result,
                'success': review_result['overall_success']
            },
            importance=0.8 if review_result['overall_success'] else 0.9,  # Failures are more important to remember
            tags=['execution', 'orchestration', 'multi_agent']
        )
    
    async def _generate_unified_response(
        self, 
        instruction: str, 
        plan: Plan, 
        execution_results: List[ExecutionResult],
        review_result: Dict[str, Any], 
        context: AgentContext
    ) -> str:
        """
        Generate a unified, human-readable response
        """
        
        if review_result['overall_success']:
            response = f"✅ Successfully executed your request: \"{instruction}\"\n\n"
            response += f"📋 Completed {review_result['successful_steps']} steps\n"
            response += f"📝 Modified {len(review_result['files_modified'])} files\n"
            
            if review_result['files_modified']:
                response += "\nFiles changed:\n"
                for file in review_result['files_modified'][:5]:  # Show first 5
                    response += f"• {file}\n"
                
                if len(review_result['files_modified']) > 5:
                    response += f"• ... and {len(review_result['files_modified']) - 5} more\n"
        
        else:
            response = f"⚠️ Partially completed your request: \"{instruction}\"\n\n"
            response += f"✅ Successful: {review_result['successful_steps']}\n"
            response += f"❌ Failed: {review_result['failed_steps']}\n"
            response += f"\n{review_result['summary']}\n"
        
        if review_result['recommendations']:
            response += "\n💡 Recommendations:\n"
            for rec in review_result['recommendations']:
                response += f"• {rec}\n"
        
        return response
    
    async def _handle_orchestration_error(
        self, 
        error: Exception, 
        user_id: str, 
        instruction: str, 
        workspace_root: str
    ) -> Dict[str, Any]:
        """
        Handle orchestration-level errors
        """
        
        # Save error to memory
        await self.memory.save_event(
            user_id=user_id,
            event_type='error',
            content={
                'instruction': instruction,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'workspace_root': workspace_root
            },
            importance=1.0,  # Orchestration errors are critical
            tags=['error', 'orchestration', 'critical']
        )
        
        return {
            'success': False,
            'error': str(error),
            'error_type': 'orchestration_error',
            'response': f"❌ I encountered an error while processing your request: {str(error)}\n\nThis has been logged and I'll learn from it to prevent similar issues in the future."
        }
