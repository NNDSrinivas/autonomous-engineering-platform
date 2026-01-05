"""
Pipeline Workflow Engine - Multi-Step Chain Execution
Enables complex automated workflows with branching, parallel execution, and context passing.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import inspect

try:
    from ..memory.episodic_memory import EpisodicMemory
except ImportError:
    from backend.memory.episodic_memory import EpisodicMemory


class StepStatus(Enum):
    """Status of a pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class PipelineStatus(Enum):
    """Status of the entire pipeline."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ExecutionMode(Enum):
    """Execution mode for steps."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


@dataclass
@dataclass
class StepResult:
    """Result of a step execution."""

    step_id: str
    status: StepStatus
    output: Any = None
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class PipelineContext:
    """Context passed through pipeline execution."""

    pipeline_id: str
    workspace_root: str
    initial_input: Dict[str, Any]
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    shared_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PipelineStep:
    """
    A single step in a pipeline workflow.
    """

    def __init__(
        self,
        step_id: str,
        name: str,
        function: Callable,
        depends_on: Optional[List[str]] = None,
        condition: Optional[Callable[[PipelineContext], bool]] = None,
        retry_count: int = 0,
        timeout_seconds: int = 300,
    ):
        """
        Initialize pipeline step.

        Args:
            step_id: Unique identifier for the step
            name: Human-readable name
            function: Function to execute (async or sync)
            depends_on: List of step IDs this step depends on
            condition: Optional condition function to determine if step should run
            retry_count: Number of retries on failure
            timeout_seconds: Timeout for step execution
        """
        self.step_id = step_id
        self.name = name
        self.function = function
        self.depends_on = depends_on or []
        self.condition = condition
        self.retry_count = retry_count
        self.timeout_seconds = timeout_seconds

        # Execution state
        self.status = StepStatus.PENDING
        self.result: Optional[StepResult] = None
        self.logger = logging.getLogger(__name__)

    async def execute(self, context: PipelineContext) -> StepResult:
        """
        Execute the step with the given context.

        Args:
            context: Pipeline execution context

        Returns:
            Step execution result
        """
        start_time = datetime.utcnow()

        # Initialize result
        result = StepResult(
            step_id=self.step_id, status=StepStatus.RUNNING, started_at=start_time
        )

        try:
            self.status = StepStatus.RUNNING

            # Check condition if specified
            if self.condition and not self.condition(context):
                result.status = StepStatus.SKIPPED
                result.output = "Step skipped due to condition"
                self.logger.info(f"Step {self.step_id} skipped due to condition")
                return result

            # Execute with retries
            for attempt in range(self.retry_count + 1):
                try:
                    # Execute with timeout
                    if inspect.iscoroutinefunction(self.function):
                        output = await asyncio.wait_for(
                            self.function(context), timeout=self.timeout_seconds
                        )
                    else:
                        # Run sync function in executor
                        output = await asyncio.get_event_loop().run_in_executor(
                            None, self.function, context
                        )

                    result.output = output
                    result.status = StepStatus.COMPLETED
                    self.status = StepStatus.COMPLETED
                    break

                except asyncio.TimeoutError:
                    error_msg = f"Step {self.step_id} timed out after {self.timeout_seconds} seconds"
                    if attempt == self.retry_count:
                        result.error = error_msg
                        result.status = StepStatus.FAILED
                        self.status = StepStatus.FAILED
                        self.logger.error(error_msg)
                    else:
                        self.logger.warning(
                            f"{error_msg}, retrying ({attempt + 1}/{self.retry_count})"
                        )

                except Exception as e:
                    error_msg = f"Step {self.step_id} failed: {str(e)}"
                    if attempt == self.retry_count:
                        result.error = error_msg
                        result.status = StepStatus.FAILED
                        self.status = StepStatus.FAILED
                        self.logger.error(error_msg)
                    else:
                        self.logger.warning(
                            f"{error_msg}, retrying ({attempt + 1}/{self.retry_count})"
                        )

        except Exception as e:
            result.error = f"Step execution framework error: {str(e)}"
            result.status = StepStatus.FAILED
            self.status = StepStatus.FAILED
            self.logger.error(f"Step {self.step_id} execution failed: {e}")

        finally:
            result.completed_at = datetime.utcnow()
            result.execution_time_seconds = (
                result.completed_at - start_time
            ).total_seconds()
            self.result = result

        return result


class PipelineWorkflow:
    """
    Main pipeline workflow engine supporting complex execution patterns.

    Features:
    - Sequential and parallel step execution
    - Conditional step execution
    - Dependency management
    - Error handling and retries
    - Context passing between steps
    - Branching and merging
    - Real-time status monitoring
    """

    def __init__(
        self,
        pipeline_id: str,
        name: str,
        steps: List[PipelineStep],
        workspace_root: str,
        memory: Optional[EpisodicMemory] = None,
        execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
    ):
        """
        Initialize pipeline workflow.

        Args:
            pipeline_id: Unique pipeline identifier
            name: Human-readable pipeline name
            steps: List of pipeline steps
            workspace_root: Workspace root directory
            memory: Episodic memory for learning
            execution_mode: Default execution mode
        """
        self.pipeline_id = pipeline_id
        self.name = name
        self.steps = {step.step_id: step for step in steps}
        self.workspace_root = Path(workspace_root)
        self.memory = memory or EpisodicMemory()
        self.execution_mode = execution_mode
        self.logger = logging.getLogger(__name__)

        # Execution state
        self.status = PipelineStatus.INITIALIZING
        self.context: Optional[PipelineContext] = None
        self.execution_graph = self._build_execution_graph()

        # Configuration
        self.config = {
            "max_parallel_steps": 5,
            "default_timeout": 300,
            "fail_fast": True,
            "save_intermediate_results": True,
        }

        self.logger.info(f"Pipeline '{name}' initialized with {len(steps)} steps")

    def _build_execution_graph(self) -> Dict[str, List[str]]:
        """
        Build execution dependency graph.

        Returns:
            Dictionary mapping step IDs to their dependencies
        """
        graph = {}

        for step_id, step in self.steps.items():
            graph[step_id] = step.depends_on.copy()

        # Validate graph (check for cycles, missing dependencies)
        self._validate_execution_graph(graph)

        return graph

    def _validate_execution_graph(self, graph: Dict[str, List[str]]):
        """Validate the execution graph for cycles and missing dependencies."""
        # Check for missing dependencies
        all_step_ids = set(graph.keys())

        for step_id, dependencies in graph.items():
            for dep in dependencies:
                if dep not in all_step_ids:
                    raise ValueError(
                        f"Step '{step_id}' depends on unknown step '{dep}'"
                    )

        # Check for cycles using DFS
        def has_cycle(node: str, visited: set, rec_stack: set) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        visited = set()
        for step_id in graph.keys():
            if step_id not in visited:
                if has_cycle(step_id, visited, set()):
                    raise ValueError("Cycle detected in pipeline dependencies")

    async def execute(
        self,
        initial_input: Dict[str, Any],
        execution_mode: Optional[ExecutionMode] = None,
    ) -> Dict[str, Any]:
        """
        Execute the pipeline workflow.

        Args:
            initial_input: Initial input data for the pipeline
            execution_mode: Override default execution mode

        Returns:
            Pipeline execution results
        """
        execution_start = datetime.utcnow()
        mode = execution_mode or self.execution_mode

        self.logger.info(f"Starting pipeline execution: {self.pipeline_id}")
        self.status = PipelineStatus.RUNNING

        # Initialize context
        self.context = PipelineContext(
            pipeline_id=self.pipeline_id,
            workspace_root=str(self.workspace_root),
            initial_input=initial_input,
            metadata={
                "execution_mode": mode.value,
                "started_at": execution_start.isoformat(),
            },
        )

        execution_result = {
            "pipeline_id": self.pipeline_id,
            "success": False,
            "execution_mode": mode.value,
            "step_results": {},
            "execution_time_seconds": 0.0,
            "error": None,
            "metadata": {},
        }

        try:
            # Execute based on mode
            if mode == ExecutionMode.SEQUENTIAL:
                step_results = await self._execute_sequential()
            elif mode == ExecutionMode.PARALLEL:
                step_results = await self._execute_parallel()
            elif mode == ExecutionMode.CONDITIONAL:
                step_results = await self._execute_conditional()
            else:
                raise ValueError(f"Unsupported execution mode: {mode}")

            # Process results
            execution_result["step_results"] = {
                step_id: {
                    "status": result.status.value,
                    "output": result.output,
                    "error": result.error,
                    "execution_time": result.execution_time_seconds,
                }
                for step_id, result in step_results.items()
            }

            # Determine overall success
            failed_steps = [
                r for r in step_results.values() if r.status == StepStatus.FAILED
            ]
            execution_result["success"] = len(failed_steps) == 0

            if failed_steps:
                self.status = PipelineStatus.FAILED
                execution_result["error"] = f"{len(failed_steps)} steps failed"
            else:
                self.status = PipelineStatus.COMPLETED

        except Exception as e:
            execution_result["error"] = str(e)
            self.status = PipelineStatus.FAILED
            self.logger.error(f"Pipeline execution failed: {e}")

        finally:
            # Calculate execution time
            execution_result["execution_time_seconds"] = (
                datetime.utcnow() - execution_start
            ).total_seconds()

            # Record in memory
            await self._record_execution_in_memory(execution_result)

        self.logger.info(
            f"Pipeline execution completed: {self.pipeline_id}, Success: {execution_result['success']}"
        )
        return execution_result

    async def _execute_sequential(self) -> Dict[str, StepResult]:
        """Execute steps sequentially based on dependency order."""
        results = {}
        executed = set()

        # Topological sort to determine execution order
        execution_order = self._topological_sort()

        for step_id in execution_order:
            if step_id in executed:
                continue

            step = self.steps[step_id]

            # Check if all dependencies are completed successfully
            dependencies_met = all(
                dep in results and results[dep].status == StepStatus.COMPLETED
                for dep in step.depends_on
            )

            if not dependencies_met:
                # Skip step if dependencies failed
                results[step_id] = StepResult(
                    step_id=step_id,
                    status=StepStatus.SKIPPED,
                    output="Dependencies not met",
                )
                continue

            # Execute step
            if self.context is None:
                self.context = PipelineContext(
                    pipeline_id=f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    workspace_root=str(Path.cwd()),
                    initial_input={},
                )
            result = await step.execute(self.context)
            results[step_id] = result

            # Update context with result
            if hasattr(self.context, "step_results"):
                self.context.step_results[step_id] = result

            # Fail fast if configured
            if (
                hasattr(result, "status")
                and result.status == StepStatus.FAILED
                and self.config.get("fail_fast", False)
            ):
                self.logger.warning(f"Failing fast due to step {step_id} failure")
                break

            executed.add(step_id)

        return results

    async def _execute_parallel(self) -> Dict[str, StepResult]:
        """Execute steps in parallel where possible."""
        results = {}
        executed = set()

        while len(executed) < len(self.steps):
            # Find steps ready to execute (dependencies met)
            ready_steps = []

            for step_id, step in self.steps.items():
                if step_id in executed:
                    continue

                dependencies_met = all(
                    dep in results and results[dep].status == StepStatus.COMPLETED
                    for dep in step.depends_on
                )

                if dependencies_met:
                    ready_steps.append(step)

            if not ready_steps:
                # No more steps can be executed
                break

            # Limit parallel execution
            ready_steps = ready_steps[: self.config["max_parallel_steps"]]

            # Execute ready steps in parallel
            tasks = [step.execute(self.context) for step in ready_steps]
            step_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for step, result in zip(ready_steps, step_results):
                step_result: StepResult
                if isinstance(result, Exception):
                    step_result = StepResult(
                        step_id=step.step_id,
                        status=StepStatus.FAILED,
                        error=str(result),
                    )
                elif isinstance(result, StepResult):
                    step_result = result
                else:
                    # Handle any other unexpected result types
                    step_result = StepResult(
                        step_id=step.step_id,
                        status=StepStatus.FAILED,
                        error=f"Unexpected result type: {type(result)}",
                    )

                results[step.step_id] = step_result
                if self.context and hasattr(self.context, "step_results"):
                    self.context.step_results[step.step_id] = step_result
                executed.add(step.step_id)

                # Check fail fast
                if step_result.status == StepStatus.FAILED and self.config.get(
                    "fail_fast", False
                ):
                    return results

        return results

    async def _execute_conditional(self) -> Dict[str, StepResult]:
        """Execute steps with conditional logic."""
        # For now, use sequential execution with condition checking
        # This could be extended to support complex branching logic
        return await self._execute_sequential()

    def _topological_sort(self) -> List[str]:
        """
        Perform topological sort on the execution graph.

        Returns:
            List of step IDs in execution order
        """
        # Kahn's algorithm
        in_degree = {step_id: 0 for step_id in self.steps.keys()}

        # Calculate in-degrees
        for step_id, dependencies in self.execution_graph.items():
            for dep in dependencies:
                in_degree[step_id] += 1

        # Queue of nodes with no incoming edges
        queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            # Reduce in-degree for dependent nodes
            for step_id, dependencies in self.execution_graph.items():
                if current in dependencies:
                    in_degree[step_id] -= 1
                    if in_degree[step_id] == 0:
                        queue.append(step_id)

        return result

    def add_step(self, step: PipelineStep):
        """Add a new step to the pipeline."""
        self.steps[step.step_id] = step
        self.execution_graph = self._build_execution_graph()

    def remove_step(self, step_id: str):
        """Remove a step from the pipeline."""
        if step_id in self.steps:
            del self.steps[step_id]
            self.execution_graph = self._build_execution_graph()

    def get_step_status(self, step_id: str) -> Optional[StepStatus]:
        """Get the status of a specific step."""
        step = self.steps.get(step_id)
        return step.status if step else None

    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get comprehensive pipeline status.

        Returns:
            Pipeline status information
        """
        step_statuses = {
            step_id: step.status.value for step_id, step in self.steps.items()
        }

        return {
            "pipeline_id": self.pipeline_id,
            "name": self.name,
            "status": self.status.value,
            "total_steps": len(self.steps),
            "step_statuses": step_statuses,
            "execution_mode": self.execution_mode.value,
            "context_available": self.context is not None,
            "configuration": self.config,
        }

    async def _record_execution_in_memory(self, execution_result: Dict[str, Any]):
        """Record pipeline execution in episodic memory."""
        try:
            event_content = f"Pipeline execution: {self.name}"
            if execution_result["success"]:
                event_content += " (SUCCESS)"
            else:
                event_content += " (FAILED)"

            failed_steps = [
                step_id
                for step_id, result in execution_result["step_results"].items()
                if result["status"] == "failed"
            ]

            await self.memory.record_event(
                event_type="system_event",
                content=event_content,
                metadata={
                    "pipeline_id": self.pipeline_id,
                    "pipeline_name": self.name,
                    "success": execution_result["success"],
                    "execution_time": execution_result["execution_time_seconds"],
                    "total_steps": len(self.steps),
                    "failed_steps": len(failed_steps),
                    "execution_mode": execution_result["execution_mode"],
                },
            )

        except Exception as e:
            self.logger.warning(f"Failed to record pipeline execution in memory: {e}")


class PipelineBuilder:
    """
    Builder class for creating complex pipelines.
    """

    def __init__(self, pipeline_id: str, name: str, workspace_root: str):
        self.pipeline_id = pipeline_id
        self.name = name
        self.workspace_root = workspace_root
        self.steps: List[PipelineStep] = []

    def add_step(
        self,
        step_id: str,
        name: str,
        function: Callable,
        depends_on: Optional[List[str]] = None,
        condition: Optional[Callable[[PipelineContext], bool]] = None,
        retry_count: int = 0,
        timeout_seconds: int = 300,
    ) -> "PipelineBuilder":
        """
        Add a step to the pipeline.

        Args:
            step_id: Unique step identifier
            name: Step name
            function: Function to execute
            depends_on: Dependencies
            condition: Execution condition
            retry_count: Retry attempts
            timeout_seconds: Timeout

        Returns:
            Self for method chaining
        """
        step = PipelineStep(
            step_id=step_id,
            name=name,
            function=function,
            depends_on=depends_on,
            condition=condition,
            retry_count=retry_count,
            timeout_seconds=timeout_seconds,
        )

        self.steps.append(step)
        return self

    def add_parallel_group(
        self, steps: List[Dict[str, Any]], group_id_prefix: str = "parallel"
    ) -> "PipelineBuilder":
        """
        Add a group of steps to execute in parallel.

        Args:
            steps: List of step definitions
            group_id_prefix: Prefix for group step IDs

        Returns:
            Self for method chaining
        """
        for i, step_def in enumerate(steps):
            step_id = f"{group_id_prefix}_{i}"
            self.add_step(
                step_id=step_id,
                name=step_def.get("name", f"Parallel Step {i}"),
                function=step_def["function"],
                depends_on=step_def.get("depends_on"),
                condition=step_def.get("condition"),
                retry_count=step_def.get("retry_count", 0),
                timeout_seconds=step_def.get("timeout_seconds", 300),
            )

        return self

    def build(
        self,
        memory: Optional[EpisodicMemory] = None,
        execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
    ) -> PipelineWorkflow:
        """
        Build the pipeline workflow.

        Args:
            memory: Episodic memory instance
            execution_mode: Default execution mode

        Returns:
            Configured pipeline workflow
        """
        return PipelineWorkflow(
            pipeline_id=self.pipeline_id,
            name=self.name,
            steps=self.steps,
            workspace_root=self.workspace_root,
            memory=memory,
            execution_mode=execution_mode,
        )


# Predefined pipeline templates
class PipelineTemplates:
    """Common pipeline templates for typical workflows."""

    @staticmethod
    def create_security_audit_pipeline(workspace_root: str) -> PipelineWorkflow:
        """Create a security audit pipeline."""

        async def scan_secrets(context: PipelineContext):
            # Placeholder for secrets scanning
            return {"secrets_found": 0, "files_scanned": 10}

        async def scan_dependencies(context: PipelineContext):
            # Placeholder for dependency scanning
            return {"vulnerabilities": [], "packages_scanned": 5}

        async def generate_report(context: PipelineContext):
            # Generate comprehensive security report
            secrets_step = context.step_results.get("scan_secrets")
            secrets_result = secrets_step.output if secrets_step else {}
            deps_step = context.step_results.get("scan_dependencies")
            deps_result = deps_step.output if deps_step else {}

            report = {
                "secrets_found": (
                    secrets_result.get("secrets_found", 0)
                    if isinstance(secrets_result, dict)
                    else 0
                ),
                "vulnerabilities": (
                    len(deps_result.get("vulnerabilities", []))
                    if isinstance(deps_result, dict)
                    else 0
                ),
                "timestamp": datetime.utcnow().isoformat(),
            }

            return report

        builder = PipelineBuilder(
            "security_audit", "Security Audit Pipeline", workspace_root
        )
        builder.add_step("scan_secrets", "Scan for Secrets", scan_secrets)
        builder.add_step("scan_dependencies", "Scan Dependencies", scan_dependencies)
        builder.add_step(
            "generate_report",
            "Generate Report",
            generate_report,
            depends_on=["scan_secrets", "scan_dependencies"],
        )

        return builder.build()

    @staticmethod
    def create_code_quality_pipeline(workspace_root: str) -> PipelineWorkflow:
        """Create a code quality assessment pipeline."""

        async def lint_code(context: PipelineContext):
            return {"lint_errors": 5, "files_checked": 20}

        async def run_tests(context: PipelineContext):
            return {"tests_passed": 45, "tests_failed": 2, "coverage": 85.5}

        async def analyze_complexity(context: PipelineContext):
            return {"cyclomatic_complexity": 3.2, "maintainability_index": 75}

        async def generate_quality_report(context: PipelineContext):
            lint_step = context.step_results.get("lint_code")
            lint_result = lint_step.output if lint_step else {}
            test_step = context.step_results.get("run_tests")
            test_result = test_step.output if test_step else {}
            complexity_step = context.step_results.get("analyze_complexity")
            complexity_result = complexity_step.output if complexity_step else {}

            return {
                "quality_score": 85,
                "lint_errors": (
                    lint_result.get("lint_errors", 0)
                    if isinstance(lint_result, dict)
                    else 0
                ),
                "test_coverage": (
                    test_result.get("coverage", 0)
                    if isinstance(test_result, dict)
                    else 0
                ),
                "complexity": (
                    complexity_result.get("cyclomatic_complexity", 0)
                    if isinstance(complexity_result, dict)
                    else 0
                ),
            }

        builder = PipelineBuilder(
            "code_quality", "Code Quality Pipeline", workspace_root
        )
        builder.add_step("lint_code", "Lint Code", lint_code)
        builder.add_step("run_tests", "Run Tests", run_tests)
        builder.add_step("analyze_complexity", "Analyze Complexity", analyze_complexity)
        builder.add_step(
            "generate_quality_report",
            "Generate Quality Report",
            generate_quality_report,
            depends_on=["lint_code", "run_tests", "analyze_complexity"],
        )

        return builder.build(execution_mode=ExecutionMode.PARALLEL)
