"""
Root Cause Analysis (RCA) Agent for Navi
Advanced debugging agent that performs step-by-step reasoning to find and fix issues.
Equivalent to Datadog RCA + Copilot debugger but with autonomous patch generation.
"""

import json
import logging
import re
import ast
import traceback
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

try:
    from ...services.llm import call_llm
    from ...memory.episodic_memory import EpisodicMemory, MemoryEventType
except ImportError:
    # Fallback imports
    from backend.services.llm import call_llm
    from backend.memory.episodic_memory import EpisodicMemory, MemoryEventType


class RCAAgent:
    """
    Root Cause Analysis Agent that performs systematic debugging using AI reasoning.

    Capabilities:
    - Chain-of-thought debugging reasoning
    - Dependency mapping and analysis
    - Code flow simulation
    - Pattern recognition from past failures
    - Automated patch generation with validation
    - Integration with memory system for learning
    """

    def __init__(self, workspace_root: str, memory: Optional[EpisodicMemory] = None):
        """
        Initialize RCA Agent with workspace and memory integration.

        Args:
            workspace_root: Root directory of the codebase
            memory: Episodic memory system for learning from past issues
        """
        self.workspace_root = Path(workspace_root)
        self.memory = memory or EpisodicMemory()
        self.logger = logging.getLogger(__name__)

        # RCA configuration
        self.max_analysis_depth = 5  # How deep to analyze call chains
        self.confidence_threshold = 0.7  # Minimum confidence for recommendations
        self.max_similar_cases = 3  # Max similar cases to retrieve from memory

        self.logger.info(f"RCAAgent initialized for workspace: {workspace_root}")

    async def analyze_failure(
        self,
        error: str,
        error_context: Optional[Dict[str, Any]] = None,
        repo_map: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive root cause analysis of a failure.

        Args:
            error: Error message or exception details
            error_context: Additional context (file, line, stack trace, etc.)
            repo_map: Repository structure and metadata

        Returns:
            Comprehensive RCA report with root cause, recommendations, and patches
        """
        analysis_start = datetime.utcnow()
        self.logger.info(f"Starting RCA analysis for error: {error[:100]}...")

        try:
            # Step 1: Parse and classify error
            error_classification = await self._classify_error(error, error_context)

            # Step 2: Retrieve similar past failures from memory
            similar_cases = await self._get_similar_failures(error)

            # Step 3: Map dependencies and affected components
            dependency_map = await self._map_dependencies(error_context, repo_map)

            # Step 4: Perform chain-of-thought analysis
            chain_analysis = await self._perform_chain_analysis(
                error, error_context, dependency_map, similar_cases
            )

            # Step 5: Generate root cause hypothesis
            root_cause = await self._identify_root_cause(
                error, error_classification, chain_analysis, similar_cases
            )

            # Step 6: Generate fix recommendations
            fix_recommendations = await self._generate_fix_recommendations(
                root_cause, error_context, dependency_map
            )

            # Step 7: Generate patches if possible
            patches = await self._generate_patches(fix_recommendations, error_context)

            # Step 8: Validate patches using AST analysis
            validated_patches = await self._validate_patches(patches, error_context)

            # Compile comprehensive RCA report
            rca_report = {
                "analysis_id": f"rca_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                "timestamp": analysis_start.isoformat(),
                "error_classification": error_classification,
                "similar_cases": similar_cases,
                "dependency_map": dependency_map,
                "chain_analysis": chain_analysis,
                "root_cause": root_cause,
                "fix_recommendations": fix_recommendations,
                "patches": validated_patches,
                "confidence_score": self._calculate_confidence_score(
                    error_classification, similar_cases, chain_analysis
                ),
                "analysis_duration_seconds": (
                    datetime.utcnow() - analysis_start
                ).total_seconds(),
            }

            # Record in memory for future learning
            await self._record_analysis_in_memory(rca_report, error)

            self.logger.info(
                f"RCA analysis completed with confidence {rca_report['confidence_score']:.2f}"
            )
            return rca_report

        except Exception as e:
            self.logger.error(f"RCA analysis failed: {e}")
            traceback.print_exc()
            return {
                "analysis_id": f"rca_failed_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                "error": str(e),
                "success": False,
                "timestamp": analysis_start.isoformat(),
            }

    async def _classify_error(
        self, error: str, error_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Classify the type and characteristics of the error.

        Args:
            error: Error message
            error_context: Additional error context

        Returns:
            Error classification with type, severity, and characteristics
        """
        classification_prompt = f"""
        Analyze this error and classify it systematically:

        ERROR: {error}
        
        CONTEXT: {json.dumps(error_context or {}, indent=2)}
        
        Provide JSON classification:
        {{
            "error_type": "syntax|runtime|logic|network|database|dependency|security|performance",
            "severity": "critical|high|medium|low",
            "category": "specific category like 'null_pointer', 'import_error', etc.",
            "affected_systems": ["list of affected systems/components"],
            "likely_causes": ["list of most probable causes"],
            "urgency": "immediate|high|normal|low",
            "complexity": "simple|moderate|complex|very_complex",
            "has_stack_trace": true/false,
            "reproducibility": "always|sometimes|rare|unknown"
        }}
        
        Base classification on actual error content and patterns.
        """

        try:
            response = await call_llm(
                message=classification_prompt,
                context={},
                model="gpt-4",
                mode="analysis",
            )

            # Parse JSON response
            classification = json.loads(response)

            # Add computed fields
            classification["analysis_timestamp"] = datetime.utcnow().isoformat()
            classification["error_hash"] = hash(error) % (
                10**8
            )  # Simple hash for tracking

            return classification

        except Exception as e:
            self.logger.warning(f"Error classification failed: {e}")
            return {
                "error_type": "unknown",
                "severity": "medium",
                "category": "unclassified",
                "error": str(e),
            }

    async def _get_similar_failures(self, error: str) -> List[Dict[str, Any]]:
        """
        Retrieve similar failures from memory system.

        Args:
            error: Error message to find similar cases for

        Returns:
            List of similar past failures with their solutions
        """
        try:
            similar_cases = await self.memory.get_similar_bug_fixes(
                error_message=error, limit=self.max_similar_cases
            )

            # Enhance with relevance scoring
            enhanced_cases = []
            for case in similar_cases:
                enhanced_case = {
                    **case,
                    "relevance_explanation": self._explain_relevance(error, case),
                    "solution_success_rate": case["metadata"].get("success", False),
                }
                enhanced_cases.append(enhanced_case)

            return enhanced_cases

        except Exception as e:
            self.logger.warning(f"Failed to retrieve similar cases: {e}")
            return []

    async def _map_dependencies(
        self,
        error_context: Optional[Dict[str, Any]],
        repo_map: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Map dependencies and affected components.

        Args:
            error_context: Error context information
            repo_map: Repository structure map

        Returns:
            Dependency mapping with affected components and relationships
        """
        try:
            # Extract file information from error context
            affected_files = []
            if error_context:
                if "file" in error_context:
                    affected_files.append(error_context["file"])
                if "stack_trace" in error_context:
                    # Parse stack trace for additional files
                    stack_files = self._extract_files_from_stack_trace(
                        error_context["stack_trace"]
                    )
                    affected_files.extend(stack_files)

            # Analyze dependencies for affected files
            dependency_analysis = {}
            for file_path in affected_files[:5]:  # Limit analysis scope
                if self.workspace_root and (self.workspace_root / file_path).exists():
                    deps = await self._analyze_file_dependencies(file_path)
                    dependency_analysis[file_path] = deps

            return {
                "affected_files": affected_files,
                "dependency_analysis": dependency_analysis,
                "repo_structure": repo_map or {},
                "dependency_graph": self._build_dependency_graph(dependency_analysis),
            }

        except Exception as e:
            self.logger.warning(f"Dependency mapping failed: {e}")
            return {"affected_files": [], "dependency_analysis": {}, "error": str(e)}

    async def _perform_chain_analysis(
        self,
        error: str,
        error_context: Optional[Dict[str, Any]],
        dependency_map: Dict[str, Any],
        similar_cases: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Perform chain-of-thought analysis to trace the error backwards.

        Args:
            error: Error message
            error_context: Error context
            dependency_map: Dependency relationships
            similar_cases: Similar past cases

        Returns:
            Chain-of-thought analysis with reasoning steps
        """
        chain_prompt = f"""
        Perform systematic chain-of-thought analysis to trace this error backwards:

        ERROR: {error}
        
        CONTEXT: {json.dumps(error_context or {}, indent=2)}
        
        DEPENDENCIES: {json.dumps(dependency_map, indent=2)}
        
        SIMILAR CASES: {json.dumps([case.get('metadata', {}) for case in similar_cases], indent=2)}
        
        Think through this step by step:
        
        1. IMMEDIATE CAUSE: What directly caused this error?
        2. CHAIN ANALYSIS: Work backwards - what led to the immediate cause?
        3. CONTRIBUTING FACTORS: What conditions allowed this to happen?
        4. ROOT CONDITION: What is the fundamental issue?
        5. PREVENTION: How could this have been prevented?
        
        Provide reasoning in JSON format:
        {{
            "immediate_cause": "direct technical cause",
            "chain_steps": [
                {{"step": 1, "description": "step description", "evidence": "supporting evidence"}},
                {{"step": 2, "description": "next step back", "evidence": "supporting evidence"}}
            ],
            "contributing_factors": ["list of factors that enabled the issue"],
            "root_condition": "fundamental underlying issue",
            "prevention_strategies": ["how to prevent similar issues"],
            "confidence_level": "high|medium|low",
            "reasoning_quality": "detailed assessment of analysis quality"
        }}
        """

        try:
            response = await call_llm(
                message=chain_prompt, context={}, model="gpt-4", mode="analysis"
            )

            analysis = json.loads(response)
            analysis["analysis_timestamp"] = datetime.utcnow().isoformat()

            return analysis

        except Exception as e:
            self.logger.warning(f"Chain analysis failed: {e}")
            return {
                "immediate_cause": "analysis_failed",
                "chain_steps": [],
                "error": str(e),
            }

    async def _identify_root_cause(
        self,
        error: str,
        error_classification: Dict[str, Any],
        chain_analysis: Dict[str, Any],
        similar_cases: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Synthesize all analysis to identify the root cause.

        Args:
            error: Original error
            error_classification: Error classification results
            chain_analysis: Chain-of-thought analysis
            similar_cases: Similar past cases

        Returns:
            Root cause identification with evidence and confidence
        """
        synthesis_prompt = f"""
        Synthesize all analysis to identify the definitive root cause:

        ORIGINAL ERROR: {error}
        
        CLASSIFICATION: {json.dumps(error_classification, indent=2)}
        
        CHAIN ANALYSIS: {json.dumps(chain_analysis, indent=2)}
        
        SIMILAR CASES: {json.dumps([case.get('metadata', {}).get('solution', 'N/A') for case in similar_cases], indent=2)}
        
        Based on all evidence, determine the root cause:
        
        {{
            "root_cause_summary": "concise root cause statement",
            "root_cause_detailed": "detailed explanation of the root cause",
            "evidence_supporting": ["list of evidence that supports this conclusion"],
            "evidence_against": ["any evidence that contradicts this conclusion"],
            "alternative_hypotheses": ["other possible root causes considered"],
            "confidence_score": 0.0-1.0,
            "certainty_factors": {{
                "technical_evidence": 0.0-1.0,
                "historical_patterns": 0.0-1.0,
                "logical_consistency": 0.0-1.0
            }},
            "risk_assessment": {{
                "likelihood_of_recurrence": "high|medium|low",
                "impact_if_not_fixed": "critical|high|medium|low",
                "fix_complexity": "simple|moderate|complex|very_complex"
            }}
        }}
        """

        try:
            response = await call_llm(
                message=synthesis_prompt, context={}, model="gpt-4", mode="analysis"
            )

            root_cause = json.loads(response)
            root_cause["identified_at"] = datetime.utcnow().isoformat()

            return root_cause

        except Exception as e:
            self.logger.warning(f"Root cause identification failed: {e}")
            return {
                "root_cause_summary": "identification_failed",
                "confidence_score": 0.0,
                "error": str(e),
            }

    async def _generate_fix_recommendations(
        self,
        root_cause: Dict[str, Any],
        error_context: Optional[Dict[str, Any]],
        dependency_map: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Generate specific fix recommendations based on root cause analysis.

        Args:
            root_cause: Root cause identification
            error_context: Error context
            dependency_map: Dependency relationships

        Returns:
            List of fix recommendations with implementation details
        """
        recommendations_prompt = f"""
        Generate specific, actionable fix recommendations:

        ROOT CAUSE: {json.dumps(root_cause, indent=2)}
        
        ERROR CONTEXT: {json.dumps(error_context or {}, indent=2)}
        
        DEPENDENCIES: {json.dumps(dependency_map, indent=2)}
        
        Generate up to 3 fix recommendations in order of preference:
        
        [
            {{
                "recommendation_id": 1,
                "title": "short descriptive title",
                "description": "detailed description of the fix",
                "implementation_steps": [
                    "step 1: specific action",
                    "step 2: specific action"
                ],
                "files_to_modify": ["list of files that need changes"],
                "risk_level": "low|medium|high",
                "effort_estimate": "small|medium|large",
                "side_effects": ["potential side effects"],
                "testing_strategy": "how to test the fix",
                "rollback_plan": "how to rollback if needed",
                "confidence": 0.0-1.0
            }}
        ]
        """

        try:
            response = await call_llm(
                message=recommendations_prompt,
                context={},
                model="gpt-4",
                mode="analysis",
            )

            recommendations = json.loads(response)

            # Enhance recommendations with metadata
            for i, rec in enumerate(recommendations):
                rec["generated_at"] = datetime.utcnow().isoformat()
                rec["priority"] = i + 1  # Priority based on order
                rec["recommendation_hash"] = hash(rec.get("title", "")) % (10**6)

            return recommendations

        except Exception as e:
            self.logger.warning(f"Fix recommendation generation failed: {e}")
            return [
                {
                    "title": "recommendation_generation_failed",
                    "description": f"Failed to generate recommendations: {e}",
                    "confidence": 0.0,
                }
            ]

    async def _generate_patches(
        self,
        recommendations: List[Dict[str, Any]],
        error_context: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Generate actual code patches for fix recommendations.

        Args:
            recommendations: Fix recommendations
            error_context: Error context with file information

        Returns:
            List of generated patches with validation info
        """
        patches = []

        for recommendation in recommendations[
            :2
        ]:  # Generate patches for top 2 recommendations
            try:
                if "files_to_modify" not in recommendation:
                    continue

                for file_path in recommendation["files_to_modify"][
                    :3
                ]:  # Limit to 3 files
                    patch = await self._generate_file_patch(
                        file_path, recommendation, error_context
                    )
                    if patch:
                        patches.append(patch)

            except Exception as e:
                self.logger.warning(
                    f"Patch generation failed for {recommendation.get('title')}: {e}"
                )

        return patches

    async def _generate_file_patch(
        self,
        file_path: str,
        recommendation: Dict[str, Any],
        error_context: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a patch for a specific file based on recommendation.

        Args:
            file_path: Path to file to patch
            recommendation: Fix recommendation
            error_context: Error context

        Returns:
            Generated patch or None if generation failed
        """
        try:
            # Read current file content
            full_path = self.workspace_root / file_path
            if not full_path.exists():
                return None

            with open(full_path, "r", encoding="utf-8") as f:
                current_content = f.read()

            # Generate patch using LLM
            patch_prompt = f"""
            Generate a precise code patch for this file:

            FILE: {file_path}
            
            CURRENT CONTENT:
            ```
            {current_content}
            ```
            
            RECOMMENDATION: {json.dumps(recommendation, indent=2)}
            
            ERROR CONTEXT: {json.dumps(error_context or {}, indent=2)}
            
            Generate a unified diff patch that implements the fix recommendation.
            Return only the patch in standard unified diff format.
            """

            response = await call_llm(
                message=patch_prompt, context={}, model="gpt-4", mode="code_generation"
            )

            # Clean and validate patch format
            patch_content = response.strip()
            if not patch_content.startswith("---"):
                # Not a proper diff, try to create one
                patch_content = f"--- {file_path}\n+++ {file_path}\n{patch_content}"

            return {
                "file_path": file_path,
                "patch_content": patch_content,
                "recommendation_id": recommendation.get("recommendation_id"),
                "generated_at": datetime.utcnow().isoformat(),
                "patch_type": "unified_diff",
                "validation_status": "pending",
            }

        except Exception as e:
            self.logger.warning(f"File patch generation failed for {file_path}: {e}")
            return None

    async def _validate_patches(
        self, patches: List[Dict[str, Any]], error_context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate generated patches using AST analysis and syntax checking.

        Args:
            patches: List of generated patches
            error_context: Error context

        Returns:
            Patches with validation results
        """
        validated_patches = []

        for patch in patches:
            try:
                validation_result = await self._validate_single_patch(
                    patch, error_context
                )
                patch.update(validation_result)
                validated_patches.append(patch)

            except Exception as e:
                patch["validation_status"] = "failed"
                patch["validation_error"] = str(e)
                validated_patches.append(patch)

        return validated_patches

    async def _validate_single_patch(
        self, patch: Dict[str, Any], error_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate a single patch for correctness and safety.

        Args:
            patch: Patch to validate
            error_context: Error context

        Returns:
            Validation results
        """
        validation_results = {
            "validation_status": "unknown",
            "syntax_valid": False,
            "ast_valid": False,
            "safety_checks": [],
            "warnings": [],
            "validation_score": 0.0,
        }

        try:
            file_path = patch["file_path"]
            patch_content = patch["patch_content"]

            # Basic syntax validation for Python files
            if file_path.endswith(".py"):
                validation_results.update(
                    await self._validate_python_patch(file_path, patch_content)
                )

            # Calculate overall validation score
            score_components = [
                validation_results.get("syntax_valid", False),
                validation_results.get("ast_valid", False),
                len(validation_results.get("warnings", [])) == 0,
            ]
            validation_results["validation_score"] = sum(score_components) / len(
                score_components
            )

            # Determine overall status
            if validation_results["validation_score"] >= 0.8:
                validation_results["validation_status"] = "passed"
            elif validation_results["validation_score"] >= 0.5:
                validation_results["validation_status"] = "warning"
            else:
                validation_results["validation_status"] = "failed"

        except Exception as e:
            validation_results["validation_status"] = "error"
            validation_results["validation_error"] = str(e)

        return validation_results

    async def _validate_python_patch(
        self, file_path: str, patch_content: str
    ) -> Dict[str, Any]:
        """
        Validate a Python file patch using AST analysis.

        Args:
            file_path: Path to Python file
            patch_content: Patch content

        Returns:
            Python-specific validation results
        """
        results = {"syntax_valid": False, "ast_valid": False, "warnings": []}

        try:
            # For now, basic validation - would need proper patch application in production
            # This is a simplified version

            full_path = self.workspace_root / file_path
            if full_path.exists():
                with open(full_path, "r") as f:
                    current_code = f.read()

                # Try to parse current code
                try:
                    ast.parse(current_code)
                    results["syntax_valid"] = True
                    results["ast_valid"] = True
                except SyntaxError as e:
                    results["warnings"].append(f"Original file has syntax errors: {e}")

        except Exception as e:
            results["warnings"].append(f"Validation failed: {e}")

        return results

    def _extract_files_from_stack_trace(self, stack_trace: str) -> List[str]:
        """
        Extract file paths from stack trace.

        Args:
            stack_trace: Stack trace text

        Returns:
            List of file paths found in stack trace
        """
        files = []
        # Simple regex to find file paths in stack traces
        file_pattern = re.compile(r'File "([^"]+)"')
        matches = file_pattern.findall(stack_trace)

        for match in matches:
            # Convert to relative path if possible
            try:
                rel_path = Path(match).relative_to(self.workspace_root)
                files.append(str(rel_path))
            except Exception:
                files.append(match)

        return list(set(files))  # Remove duplicates

    async def _analyze_file_dependencies(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze dependencies for a specific file.

        Args:
            file_path: Path to file to analyze

        Returns:
            Dependency analysis results
        """
        # Simplified dependency analysis - would be more sophisticated in production
        try:
            full_path = self.workspace_root / file_path
            if not full_path.exists():
                return {}

            dependencies = {"imports": [], "internal_calls": [], "external_calls": []}

            if file_path.endswith(".py"):
                # Python dependency analysis
                with open(full_path, "r") as f:
                    content = f.read()

                # Extract imports
                import_pattern = re.compile(
                    r"^(?:from\s+(\S+)\s+)?import\s+(.+)", re.MULTILINE
                )
                for match in import_pattern.finditer(content):
                    module = match.group(1) or match.group(2).split(".")[0]
                    dependencies["imports"].append(module)

            return dependencies

        except Exception as e:
            self.logger.warning(f"Dependency analysis failed for {file_path}: {e}")
            return {}

    def _build_dependency_graph(
        self, dependency_analysis: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """
        Build a simple dependency graph from analysis.

        Args:
            dependency_analysis: Dependency analysis results

        Returns:
            Simple dependency graph
        """
        graph = {}
        for file_path, deps in dependency_analysis.items():
            graph[file_path] = deps.get("imports", [])
        return graph

    def _explain_relevance(self, current_error: str, past_case: Dict[str, Any]) -> str:
        """
        Explain why a past case is relevant to the current error.

        Args:
            current_error: Current error message
            past_case: Past case from memory

        Returns:
            Explanation of relevance
        """
        # Simplified relevance explanation
        similarity_score = past_case.get("similarity", 0.0)

        if similarity_score > 0.8:
            return "Very similar error pattern and context"
        elif similarity_score > 0.6:
            return "Similar error with some contextual differences"
        elif similarity_score > 0.4:
            return "Related error type, different context"
        else:
            return "Possibly related pattern"

    def _calculate_confidence_score(
        self,
        error_classification: Dict[str, Any],
        similar_cases: List[Dict[str, Any]],
        chain_analysis: Dict[str, Any],
    ) -> float:
        """
        Calculate overall confidence score for the RCA analysis.

        Args:
            error_classification: Error classification results
            similar_cases: Similar past cases
            chain_analysis: Chain-of-thought analysis

        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence_factors = []

        # Classification confidence
        if error_classification.get("error_type") != "unknown":
            confidence_factors.append(0.8)
        else:
            confidence_factors.append(0.3)

        # Similar cases boost confidence
        if similar_cases:
            avg_similarity = sum(
                case.get("similarity", 0.0) for case in similar_cases
            ) / len(similar_cases)
            confidence_factors.append(avg_similarity)
        else:
            confidence_factors.append(0.4)  # No similar cases, moderate confidence

        # Chain analysis quality
        chain_confidence = chain_analysis.get("confidence_level", "low")
        if chain_confidence == "high":
            confidence_factors.append(0.9)
        elif chain_confidence == "medium":
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.5)

        return sum(confidence_factors) / len(confidence_factors)

    async def _record_analysis_in_memory(
        self, rca_report: Dict[str, Any], original_error: str
    ):
        """
        Record the RCA analysis in memory for future learning.

        Args:
            rca_report: Complete RCA analysis report
            original_error: Original error that was analyzed
        """
        try:
            # Record the analysis event
            await self.memory.record_event(
                event_type=MemoryEventType.ERROR_ENCOUNTERED,
                content=f"RCA Analysis: {original_error[:200]}",
                metadata={
                    "rca_report_id": rca_report["analysis_id"],
                    "error_classification": rca_report.get("error_classification", {}),
                    "root_cause": rca_report.get("root_cause", {}),
                    "confidence_score": rca_report.get("confidence_score", 0.0),
                    "fixes_generated": len(rca_report.get("patches", [])),
                    "analysis_successful": rca_report.get("confidence_score", 0.0)
                    > self.confidence_threshold,
                },
            )

            self.logger.debug(
                f"Recorded RCA analysis {rca_report['analysis_id']} in memory"
            )

        except Exception as e:
            self.logger.warning(f"Failed to record RCA analysis in memory: {e}")
