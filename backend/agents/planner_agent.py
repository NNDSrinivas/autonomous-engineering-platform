from typing import List, Dict, Any, Optional
import json
from datetime import datetime

try:
    from ..models.plan import PlanStep, Plan
    from ..services.llm import call_llm
    from ..services.llm_router import LLMRouter
    from ..core.config import get_settings
except ImportError:
    from backend.models.plan import PlanStep, Plan
    from backend.services.llm import call_llm
    from backend.services.llm_router import LLMRouter
    from backend.core.config import get_settings


class PlannerAgent:
    """
    The Planner Agent converts user instructions into structured, executable plans.
    This is the strategic brain that breaks down complex engineering tasks into
    actionable steps with proper dependencies and context requirements.
    """

    def __init__(self):
        self.llm_router = LLMRouter()
        self.settings = get_settings()

    async def generate_plan(
        self,
        instruction: str,
        repo_map: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Plan:
        """
        Converts user instruction into a structured multi-step execution plan.

        This is the core intelligence that makes Navi autonomous - it understands
        user intent and creates a comprehensive execution strategy.
        """

        # Analyze instruction complexity and scope
        complexity_score = await self._analyze_instruction_complexity(
            instruction, repo_map
        )

        # Generate the plan using LLM with structured prompting
        plan_steps = await self._generate_plan_steps(
            instruction, repo_map, user_context
        )

        # Post-process and validate the plan
        validated_steps = await self._validate_and_optimize_plan(plan_steps, repo_map)

        # Calculate estimated execution time
        total_time = sum(step.estimated_duration for step in validated_steps)

        return Plan(
            id=f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            steps=validated_steps,
            estimated_duration=total_time,
            complexity_score=complexity_score,
            status="ready",
        )

    async def plan(self, intent: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 4.1.2 compatibility method for orchestrator
        """
        instruction = getattr(intent, "raw_text", str(intent))
        repo_map = context.get("repo_map", {})

        plan_result = await self.generate_plan(instruction, repo_map, context)

        return {
            "success": True,
            "plan": plan_result,
            "reasoning": f"Generated plan with {len(plan_result.steps)} steps",
        }

    async def _analyze_instruction_complexity(
        self, instruction: str, repo_map: Dict[str, Any]
    ) -> float:
        """
        Analyze the complexity of the user instruction to inform planning strategy
        """

        complexity_prompt = f"""
        Analyze the complexity of this engineering instruction on a scale of 0.0 to 1.0:

        Instruction: {instruction}

        Repository context:
        - Total files: {repo_map.get("total_files", 0)}
        - Languages: {repo_map.get("languages", {})}
        - Architecture: {repo_map.get("architecture", {})}
        
        Consider:
        - Scope (single file vs multi-file vs architecture change)
        - Technical complexity (simple edit vs refactoring vs new feature)
        - Dependencies (isolated vs cross-cutting concerns)
        - Risk level (safe changes vs potentially breaking changes)
        
        Return only a decimal number between 0.0 and 1.0.
        """

        try:
            response = await call_llm(
                message=complexity_prompt, context={}, model="gpt-4"
            )

            complexity = float(response.strip())
            return max(0.0, min(1.0, complexity))  # Clamp to valid range

        except (ValueError, AttributeError):
            # Fallback: estimate based on keywords
            return self._estimate_complexity_fallback(instruction, repo_map)

    def _estimate_complexity_fallback(
        self, instruction: str, repo_map: Dict[str, Any]
    ) -> float:
        """
        Fallback complexity estimation based on keywords and repo size
        """
        instruction_lower = instruction.lower()

        # High complexity indicators
        high_complexity_keywords = [
            "refactor",
            "architecture",
            "redesign",
            "migrate",
            "convert",
            "performance",
            "optimization",
            "security",
            "testing",
            "ci/cd",
        ]

        # Medium complexity indicators
        medium_complexity_keywords = [
            "feature",
            "component",
            "service",
            "api",
            "database",
            "integration",
            "update",
            "enhance",
            "improve",
        ]

        # Calculate base complexity
        base_complexity = 0.3

        # Adjust based on keywords
        for keyword in high_complexity_keywords:
            if keyword in instruction_lower:
                base_complexity += 0.2

        for keyword in medium_complexity_keywords:
            if keyword in instruction_lower:
                base_complexity += 0.1

        # Adjust based on repo size
        file_count = repo_map.get("total_files", 0)
        if file_count > 100:
            base_complexity += 0.1
        if file_count > 500:
            base_complexity += 0.1

        return min(1.0, base_complexity)

    async def _generate_plan_steps(
        self,
        instruction: str,
        repo_map: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> List[PlanStep]:
        """
        Generate detailed plan steps using LLM
        """

        # Build context-aware prompt
        prompt = self._build_planning_prompt(instruction, repo_map, user_context)

        try:
            response = await self.llm_router.run(
                prompt=prompt, use_smart_auto=True, max_tokens=2000
            )

            # Parse LLM response into structured steps
            steps = PlanStep.parse_steps(response.text)

            # Ensure each step has a unique ID
            for i, step in enumerate(steps):
                if not step.id:
                    step.id = f"step_{i + 1}"

            return steps

        except Exception:
            # Fallback: create basic plan
            return self._create_fallback_plan(instruction, repo_map)

    def _build_planning_prompt(
        self,
        instruction: str,
        repo_map: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build comprehensive planning prompt for the LLM
        """

        context_section = ""
        if user_context:
            recent_history = user_context.get("recent_history", [])
            if recent_history:
                context_section = f"""
                Recent user activity:
                {json.dumps(recent_history[-3:], indent=2)}
                """

        return f"""
        You are Navi Planner, an expert software engineering agent. Convert the following user instruction into a detailed JSON array of execution steps.

        User instruction: {instruction}

        Repository context:
        - Root path: {repo_map.get("root_path", "")}
        - Total files: {repo_map.get("total_files", 0)}
        - Languages: {json.dumps(repo_map.get("languages", {}), indent=2)}
        - Key files: {json.dumps(repo_map.get("hotspots", [])[:10], indent=2)}
        - Architecture: {json.dumps(repo_map.get("architecture", {}), indent=2)}
        
        {context_section}

        Create a JSON array where each step has:
        {{
            "id": "unique_step_identifier",
            "action_type": "modify_file|refactor|search_code|apply_patch|run_command|review|ask_clarification",
            "file_targets": ["list", "of", "target", "files"],
            "description": "clear description of what this step does",
            "required_context": ["what context/info is needed before this step"],
            "depends_on": ["list", "of", "step_ids", "that", "must", "complete", "first"],
            "priority": 1,  // 1=high, 2=medium, 3=low
            "estimated_duration": 120,  // seconds
            "metadata": {{
                "safety_level": "safe|moderate|risky",
                "reversible": true,
                "backup_recommended": false
            }}
        }}

        Action types guide:
        - "search_code": Find relevant code patterns, functions, or usage
        - "modify_file": Direct file edits, additions, deletions
        - "refactor": Structural code changes using AST transforms
        - "apply_patch": Apply generated diffs/patches
        - "run_command": Execute shell commands, tests, builds
        - "review": Validate changes, run analysis, check quality
        - "ask_clarification": Request more info from user

        Guidelines:
        1. Break complex tasks into smaller, focused steps
        2. Include proper dependency chains
        3. Add context-gathering steps before modifications
        4. Include review/validation steps after changes
        5. Consider backup/rollback for risky operations
        6. Estimate realistic time requirements
        
        Return ONLY the JSON array, no additional text.
        """

    def _create_fallback_plan(
        self, instruction: str, repo_map: Dict[str, Any]
    ) -> List[PlanStep]:
        """
        Create a basic fallback plan when LLM parsing fails
        """

        steps = []
        instruction_lower = instruction.lower()

        # Analyze instruction to determine basic steps
        if "refactor" in instruction_lower:
            steps.extend(
                [
                    PlanStep(
                        id="analyze_code",
                        action_type="search_code",
                        file_targets=[],
                        description="Analyze existing code structure",
                        required_context=[],
                        depends_on=[],
                    ),
                    PlanStep(
                        id="plan_refactor",
                        action_type="review",
                        file_targets=[],
                        description="Plan refactoring approach",
                        required_context=["code_analysis"],
                        depends_on=["analyze_code"],
                    ),
                    PlanStep(
                        id="apply_refactor",
                        action_type="refactor",
                        file_targets=[],
                        description="Apply refactoring changes",
                        required_context=["refactor_plan"],
                        depends_on=["plan_refactor"],
                    ),
                ]
            )

        elif any(keyword in instruction_lower for keyword in ["fix", "bug", "error"]):
            steps.extend(
                [
                    PlanStep(
                        id="identify_issue",
                        action_type="search_code",
                        file_targets=[],
                        description="Identify the issue location",
                        required_context=[],
                        depends_on=[],
                    ),
                    PlanStep(
                        id="apply_fix",
                        action_type="modify_file",
                        file_targets=[],
                        description="Apply the fix",
                        required_context=["issue_location"],
                        depends_on=["identify_issue"],
                    ),
                    PlanStep(
                        id="validate_fix",
                        action_type="run_command",
                        file_targets=[],
                        description="Test the fix",
                        required_context=[],
                        depends_on=["apply_fix"],
                    ),
                ]
            )

        else:
            # Generic modification plan
            steps.extend(
                [
                    PlanStep(
                        id="understand_request",
                        action_type="search_code",
                        file_targets=[],
                        description="Understand the requested changes",
                        required_context=[],
                        depends_on=[],
                    ),
                    PlanStep(
                        id="make_changes",
                        action_type="modify_file",
                        file_targets=[],
                        description="Implement the requested changes",
                        required_context=["understanding"],
                        depends_on=["understand_request"],
                    ),
                    PlanStep(
                        id="review_changes",
                        action_type="review",
                        file_targets=[],
                        description="Review and validate changes",
                        required_context=[],
                        depends_on=["make_changes"],
                    ),
                ]
            )

        return steps

    async def _validate_and_optimize_plan(
        self, steps: List[PlanStep], repo_map: Dict[str, Any]
    ) -> List[PlanStep]:
        """
        Validate plan steps and optimize execution order
        """

        # Validate dependencies
        step_ids = {step.id for step in steps}
        for step in steps:
            # Remove invalid dependencies
            step.depends_on = [dep for dep in step.depends_on if dep in step_ids]

        # Detect circular dependencies
        steps = self._resolve_circular_dependencies(steps)

        # Optimize execution order
        steps = self._optimize_execution_order(steps)

        # Add file targets based on repo map
        steps = await self._enrich_file_targets(steps, repo_map)

        return steps

    def _resolve_circular_dependencies(self, steps: List[PlanStep]) -> List[PlanStep]:
        """
        Detect and resolve circular dependencies in the plan
        """
        # Simple cycle detection and resolution
        # In a production system, this would be more sophisticated

        step_map = {step.id: step for step in steps}

        def has_cycle(step_id: str, visited: set, path: set) -> bool:
            if step_id in path:
                return True
            if step_id in visited:
                return False

            visited.add(step_id)
            path.add(step_id)

            step = step_map.get(step_id)
            if step:
                for dep in step.depends_on:
                    if has_cycle(dep, visited, path):
                        return True

            path.remove(step_id)
            return False

        # Remove circular dependencies
        for step in steps:
            visited = set()
            for dep in step.depends_on[:]:  # Copy list to modify during iteration
                if has_cycle(dep, visited, {step.id}):
                    step.depends_on.remove(dep)

        return steps

    def _optimize_execution_order(self, steps: List[PlanStep]) -> List[PlanStep]:
        """
        Optimize step order for efficient execution
        """
        # Topological sort to respect dependencies
        # Priority-based ordering for independent steps

        def topological_sort(steps: List[PlanStep]) -> List[PlanStep]:
            step_map = {step.id: step for step in steps}
            in_degree = {step.id: len(step.depends_on) for step in steps}
            queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
            result = []

            while queue:
                # Sort by priority (lower number = higher priority)
                queue.sort(key=lambda sid: step_map[sid].priority)
                current_id = queue.pop(0)
                result.append(step_map[current_id])

                # Update in-degrees
                for step in steps:
                    if current_id in step.depends_on:
                        in_degree[step.id] -= 1
                        if in_degree[step.id] == 0:
                            queue.append(step.id)

            return result

        return topological_sort(steps)

    async def _enrich_file_targets(
        self, steps: List[PlanStep], repo_map: Dict[str, Any]
    ) -> List[PlanStep]:
        """
        Enrich steps with specific file targets based on repo analysis
        """

        hotspots = repo_map.get("hotspots", [])

        for step in steps:
            if not step.file_targets and step.action_type in [
                "modify_file",
                "refactor",
                "search_code",
            ]:
                # Suggest relevant files based on step description
                if "test" in step.description.lower():
                    # Add test files
                    test_files = [f for f in hotspots if "test" in f.lower()]
                    step.file_targets.extend(test_files[:3])

                elif "config" in step.description.lower():
                    # Add config files
                    config_files = [
                        f
                        for f in hotspots
                        if any(
                            ext in f
                            for ext in [".json", ".yaml", ".yml", ".toml", ".ini"]
                        )
                    ]
                    step.file_targets.extend(config_files[:3])

                else:
                    # Add main source files
                    step.file_targets.extend(hotspots[:5])

        return steps

    async def replan(
        self,
        original_plan: Plan,
        execution_results: List[Dict[str, Any]],
        new_context: Optional[Dict[str, Any]] = None,
    ) -> Plan:
        """
        Regenerate plan based on execution results and new context
        """

        # Analyze what went wrong or changed
        failed_steps = [r for r in execution_results if not r.get("success", True)]

        # Build replanning prompt
        replan_prompt = f"""
        The original plan has encountered issues. Replan the remaining steps.
        
        Original instruction: {original_plan.user_instruction}
        Original plan: {json.dumps([step.dict() for step in original_plan.steps], indent=2)}
        
        Execution results:
        {json.dumps(execution_results, indent=2)}
        
        Failed steps: {len(failed_steps)}
        
        Generate a revised plan that:
        1. Addresses the failures
        2. Incorporates lessons learned
        3. Continues toward the original goal
        4. Uses the same JSON format as before
        """

        try:
            response = await self.llm_router.run(
                prompt=replan_prompt, use_smart_auto=True, max_tokens=2000
            )

            new_steps = PlanStep.parse_steps(response.text)

            # Create new plan
            new_plan = Plan(
                id=f"replan_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                user_instruction=original_plan.user_instruction,
                steps=new_steps,
                created_at=datetime.now(),
                estimated_total_time=sum(step.estimated_duration for step in new_steps),
                complexity_score=original_plan.complexity_score,
                repo_context=original_plan.repo_context,
            )

            return new_plan

        except Exception:
            # Fallback: continue with remaining original steps
            remaining_steps = [
                step
                for step in original_plan.steps
                if not any(
                    r.get("step_id") == step.id and r.get("success")
                    for r in execution_results
                )
            ]

            original_plan.steps = remaining_steps
            return original_plan
