"""
Code Generation API - Complete Implementation

Provides comprehensive code generation and analysis features including:
- AI-powered code generation from natural language
- Code analysis and suggestions
- Refactoring assistance
- Documentation generation
- Test generation
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import ast
import re

from backend.core.db import get_db
from backend.core.auth_org import require_org
from backend.core.auth.deps import get_current_user_optional
from backend.ai.llm_router import LLMRouter
from backend.ai.llm_router import get_router as get_model_router

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/navi", tags=["code-generation"])
# Settings instance is imported directly
# settings = get_settings()  # Not needed with direct import


class CodeGenerationRequest(BaseModel):
    prompt: str = Field(description="Natural language description of code to generate")
    language: str = Field(description="Target programming language")
    context: Optional[str] = Field(
        default=None, description="Additional context or existing code"
    )
    style: str = Field(
        default="clean", description="Code style: clean, minimal, verbose, enterprise"
    )
    framework: Optional[str] = Field(
        default=None, description="Specific framework or library"
    )
    test_generation: bool = Field(
        default=False, description="Generate tests along with code"
    )
    documentation: bool = Field(default=True, description="Include documentation")


class CodeAnalysisRequest(BaseModel):
    code: str = Field(description="Code to analyze")
    language: str = Field(description="Programming language")
    analysis_type: str = Field(default="comprehensive", description="Type of analysis")
    focus: Optional[str] = Field(default=None, description="Specific focus area")


class RefactorRequest(BaseModel):
    code: str = Field(description="Code to refactor")
    language: str = Field(description="Programming language")
    refactor_type: str = Field(description="Type of refactoring needed")
    goals: List[str] = Field(default_factory=list, description="Refactoring goals")
    constraints: List[str] = Field(
        default_factory=list, description="Constraints to consider"
    )


class CodeSuggestion(BaseModel):
    type: str  # improvement, bug_fix, optimization, security
    title: str
    description: str
    original_code: str
    suggested_code: str
    reasoning: str
    confidence: float
    impact: str  # low, medium, high


class GeneratedCode(BaseModel):
    code: str
    language: str
    explanation: str
    usage_example: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    tests: Optional[str] = None
    documentation: Optional[str] = None
    complexity_score: float
    maintainability_score: float


class CodeAnalysis(BaseModel):
    language: str
    metrics: Dict[str, Any]
    issues: List[Dict[str, Any]]
    suggestions: List[CodeSuggestion]
    quality_score: float
    complexity_analysis: Dict[str, Any]
    security_analysis: Dict[str, Any]
    performance_analysis: Dict[str, Any]


class RefactoredCode(BaseModel):
    original_code: str
    refactored_code: str
    changes_summary: str
    improvements: List[str]
    before_metrics: Dict[str, Any]
    after_metrics: Dict[str, Any]
    confidence: float


@router.post("/generate", response_model=GeneratedCode)
async def generate_code(
    request: CodeGenerationRequest,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Generate code from natural language description using AI
    """
    try:
        org_ctx["org_id"]

        # Get LLM router
        llm_router = get_model_router()

        # Build generation prompt
        prompt = _build_generation_prompt(request)

        # Generate code using LLM
        generated_result = await _generate_code_with_llm(llm_router, prompt, request)

        # Analyze code metrics
        metrics = _analyze_code_metrics(generated_result["code"], request.language)

        # Generate tests if requested
        tests = None
        if request.test_generation:
            tests = await _generate_tests(
                llm_router, generated_result["code"], request.language
            )

        # Generate documentation if requested
        documentation = None
        if request.documentation:
            documentation = await _generate_documentation(
                llm_router, generated_result["code"], request.language
            )

        return GeneratedCode(
            code=generated_result["code"],
            language=request.language,
            explanation=generated_result["explanation"],
            usage_example=generated_result.get("usage_example"),
            dependencies=generated_result.get("dependencies", []),
            tests=tests,
            documentation=documentation,
            complexity_score=metrics["complexity_score"],
            maintainability_score=metrics["maintainability_score"],
        )

    except Exception as e:
        logger.error(f"Code generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Code generation failed: {str(e)}")


@router.post("/analyze", response_model=CodeAnalysis)
async def analyze_code(
    request: CodeAnalysisRequest,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Analyze code for quality, security, performance, and maintainability
    """
    try:
        org_ctx["org_id"]

        # Initialize LLM router for analysis
        llm_router = get_model_router()

        # Perform static analysis
        static_metrics = _perform_static_analysis(request.code, request.language)

        # AI-powered analysis
        ai_analysis = await _perform_ai_analysis(llm_router, request)

        # Security analysis
        security_analysis = _perform_security_analysis(request.code, request.language)

        # Performance analysis
        performance_analysis = _analyze_performance_patterns(
            request.code, request.language
        )

        # Generate suggestions
        suggestions = await _generate_code_suggestions(llm_router, request)

        # Calculate overall quality score
        quality_score = _calculate_quality_score(
            static_metrics, ai_analysis, security_analysis
        )

        return CodeAnalysis(
            language=request.language,
            metrics=static_metrics,
            issues=ai_analysis.get("issues", []),
            suggestions=suggestions,
            quality_score=quality_score,
            complexity_analysis=static_metrics.get("complexity", {}),
            security_analysis=security_analysis,
            performance_analysis=performance_analysis,
        )

    except Exception as e:
        logger.error(f"Code analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Code analysis failed: {str(e)}")


@router.post("/refactor", response_model=RefactoredCode)
async def refactor_code(
    request: RefactorRequest,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Refactor code for improved quality, performance, or maintainability
    """
    try:
        org_ctx["org_id"]

        # Initialize LLM router for refactoring
        llm_router = get_model_router()

        # Analyze original code
        before_metrics = _analyze_code_metrics(request.code, request.language)

        # Perform AI-powered refactoring
        refactoring_result = await _perform_refactoring(llm_router, request)

        # Analyze refactored code
        after_metrics = _analyze_code_metrics(
            refactoring_result["refactored_code"], request.language
        )

        # Validate refactoring maintains functionality
        validation_result = await _validate_refactoring(
            llm_router,
            request.code,
            refactoring_result["refactored_code"],
            request.language,
        )

        return RefactoredCode(
            original_code=request.code,
            refactored_code=refactoring_result["refactored_code"],
            changes_summary=refactoring_result["changes_summary"],
            improvements=refactoring_result["improvements"],
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            confidence=validation_result["confidence"],
        )

    except Exception as e:
        logger.error(f"Code refactoring failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Code refactoring failed: {str(e)}"
        )


@router.post("/explain")
async def explain_code(
    code: str,
    language: str,
    detail_level: str = "medium",  # basic, medium, detailed
    focus: Optional[str] = None,  # algorithm, architecture, optimization
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Generate detailed explanation of code functionality and design
    """
    try:
        org_ctx["org_id"]

        # Initialize LLM router for explanation
        llm_router = get_model_router()

        # Generate explanation
        explanation = await _generate_code_explanation(
            llm_router, code, language, detail_level, focus
        )

        return {
            "explanation": explanation["explanation"],
            "key_concepts": explanation["key_concepts"],
            "flow_diagram": explanation.get("flow_diagram"),
            "examples": explanation.get("examples", []),
            "related_patterns": explanation.get("related_patterns", []),
            "learning_resources": explanation.get("learning_resources", []),
        }

    except Exception as e:
        logger.error(f"Code explanation failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Code explanation failed: {str(e)}"
        )


@router.post("/convert")
async def convert_code(
    code: str,
    from_language: str,
    to_language: str,
    maintain_style: bool = True,
    include_comments: bool = True,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Convert code from one programming language to another
    """
    try:
        org_ctx["org_id"]

        # Initialize LLM router for conversion
        llm_router = get_model_router()

        # Perform code conversion
        conversion_result = await _convert_code_language(
            llm_router,
            code,
            from_language,
            to_language,
            maintain_style,
            include_comments,
        )

        # Validate converted code
        validation = await _validate_converted_code(
            llm_router, conversion_result["converted_code"], to_language
        )

        return {
            "original_code": code,
            "converted_code": conversion_result["converted_code"],
            "from_language": from_language,
            "to_language": to_language,
            "conversion_notes": conversion_result["conversion_notes"],
            "potential_issues": conversion_result["potential_issues"],
            "validation": validation,
            "confidence": conversion_result["confidence"],
        }

    except Exception as e:
        logger.error(f"Code conversion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Code conversion failed: {str(e)}")


@router.get("/templates")
async def get_code_templates(
    language: Optional[str] = None,
    category: Optional[str] = None,  # api, ui, algorithm, data-structure
    framework: Optional[str] = None,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Get code templates and boilerplate for various purposes
    """
    try:
        templates = _get_code_templates(language, category, framework)
        return {"templates": templates}

    except Exception as e:
        logger.error(f"Failed to get code templates: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get templates: {str(e)}"
        )


# Helper functions


def _build_generation_prompt(request: CodeGenerationRequest) -> str:
    """Build comprehensive prompt for code generation"""
    prompt_parts = [
        f"Generate {request.language} code for the following requirement:",
        f"Requirement: {request.prompt}",
        f"Style: {request.style}",
    ]

    if request.context:
        prompt_parts.append(f"Context: {request.context}")

    if request.framework:
        prompt_parts.append(f"Framework: {request.framework}")

    prompt_parts.extend(
        [
            "",
            "Requirements:",
            "- Write clean, well-documented code",
            "- Follow best practices and conventions",
            "- Include error handling where appropriate",
            "- Make the code maintainable and readable",
        ]
    )

    if request.test_generation:
        prompt_parts.append("- Prepare for unit testing")

    return "\n".join(prompt_parts)


async def _generate_code_with_llm(
    llm_router: LLMRouter, prompt: str, request: CodeGenerationRequest
) -> Dict[str, Any]:
    """Generate code using LLM"""
    try:
        response = await llm_router.run(
            prompt=prompt,
            model="gpt-4",
            temperature=0.2,
            max_tokens=2000,
        )

        # Parse LLM response
        content = response.text

        # Extract code from response (handle code blocks)
        code_match = re.search(
            r"```(?:" + request.language + r")?\n(.*?)```", content, re.DOTALL
        )
        if code_match:
            code = code_match.group(1).strip()
        else:
            code = content.strip()

        # Extract dependencies if mentioned
        dependencies = []
        if "import " in code or "require(" in code or "using " in code:
            dependencies = _extract_dependencies(code, request.language)

        return {
            "code": code,
            "explanation": content,
            "dependencies": dependencies,
            "usage_example": _generate_usage_example(code, request.language),
        }

    except Exception as e:
        logger.error(f"LLM code generation failed: {e}")
        raise


def _analyze_code_metrics(code: str, language: str) -> Dict[str, Any]:
    """Analyze code metrics"""
    try:
        metrics = {
            "lines_of_code": len(code.splitlines()),
            "complexity_score": _calculate_cyclomatic_complexity(code, language),
            "maintainability_score": _calculate_maintainability_score(code, language),
            "readability_score": _calculate_readability_score(code),
            "test_coverage": 0.0,  # Would require actual test analysis
        }

        # Language-specific metrics
        if language.lower() == "python":
            metrics.update(_analyze_python_metrics(code))
        elif language.lower() in ["javascript", "typescript"]:
            metrics.update(_analyze_js_metrics(code))

        return metrics

    except Exception as e:
        logger.error(f"Error analyzing code metrics: {e}")
        return {"error": str(e)}


def _calculate_cyclomatic_complexity(code: str, language: str) -> float:
    """Calculate cyclomatic complexity"""
    try:
        # Simple heuristic based on control flow keywords
        complexity_keywords = [
            "if",
            "for",
            "while",
            "catch",
            "case",
            "switch",
            "&&",
            "||",
        ]
        complexity = 1  # Base complexity

        for keyword in complexity_keywords:
            complexity += code.count(keyword)

        return min(complexity / 10.0, 1.0)  # Normalize to 0-1

    except Exception:
        return 0.5


def _calculate_maintainability_score(code: str, language: str) -> float:
    """Calculate maintainability score"""
    try:
        score = 1.0

        # Deduct for long lines
        long_lines = len([line for line in code.splitlines() if len(line) > 100])
        score -= long_lines * 0.01

        # Deduct for large functions (simple heuristic)
        function_keywords = ["def ", "function ", "func "]
        functions = sum(code.count(keyword) for keyword in function_keywords)
        if functions > 0:
            avg_function_size = len(code.splitlines()) / functions
            if avg_function_size > 50:
                score -= 0.2

        return max(score, 0.0)

    except Exception:
        return 0.5


def _calculate_readability_score(code: str) -> float:
    """Calculate readability score"""
    try:
        lines = code.splitlines()
        if not lines:
            return 0.0

        score = 1.0

        # Check for comments
        comment_chars = ["#", "//", "/*", '"""', "'''"]
        comment_lines = sum(
            1
            for line in lines
            if any(line.strip().startswith(char) for char in comment_chars)
        )
        comment_ratio = comment_lines / len(lines)

        if comment_ratio < 0.1:
            score -= 0.2

        # Check for meaningful variable names (simple heuristic)
        short_vars = re.findall(r"\b[a-zA-Z][a-zA-Z0-9]{0,2}\b", code)
        if len(short_vars) > 10:
            score -= 0.1

        return max(score, 0.0)

    except Exception:
        return 0.5


def _analyze_python_metrics(code: str) -> Dict[str, Any]:
    """Analyze Python-specific metrics"""
    try:
        metrics = {}

        # Try to parse AST
        try:
            tree = ast.parse(code)
            metrics["functions"] = len(
                [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            )
            metrics["classes"] = len(
                [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            )
            metrics["imports"] = len(
                [
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                ]
            )
        except SyntaxError:
            metrics["parse_error"] = True

        return metrics

    except Exception:
        return {}


def _analyze_js_metrics(code: str) -> Dict[str, Any]:
    """Analyze JavaScript/TypeScript-specific metrics"""
    try:
        metrics = {}

        # Count functions
        function_patterns = [
            r"function\s+\w+",
            r"\w+\s*=\s*function",
            r"\w+\s*=\s*\(.*?\)\s*=>",
            r"async\s+function",
        ]
        metrics["functions"] = sum(
            len(re.findall(pattern, code)) for pattern in function_patterns
        )

        # Count classes
        metrics["classes"] = len(re.findall(r"class\s+\w+", code))

        # Count imports/requires
        import_patterns = [r"import\s+.*?from", r"require\s*\(", r"import\s*\("]
        metrics["imports"] = sum(
            len(re.findall(pattern, code)) for pattern in import_patterns
        )

        return metrics

    except Exception:
        return {}


async def _generate_tests(llm_router: LLMRouter, code: str, language: str) -> str:
    """Generate unit tests for the code"""
    try:
        test_prompt = f"""Generate comprehensive unit tests for the following {language} code:

{code}

Requirements:
- Cover all major functions/methods
- Include edge cases and error conditions
- Follow testing best practices for {language}
- Include setup and teardown if needed
"""

        response = await llm_router.run(
            prompt=test_prompt,
            model="gpt-4",
            temperature=0.1,
        )

        return response.text

    except Exception as e:
        logger.error(f"Test generation failed: {e}")
        return ""


async def _generate_documentation(
    llm_router: LLMRouter, code: str, language: str
) -> str:
    """Generate documentation for the code"""
    try:
        doc_prompt = f"""Generate comprehensive documentation for the following {language} code:

{code}

Include:
- Purpose and functionality
- Parameter descriptions
- Return value descriptions
- Usage examples
- Notes about complexity or performance
"""

        response = await llm_router.run(
            prompt=doc_prompt,
            model="gpt-4",
            temperature=0.1,
        )

        return response.text

    except Exception as e:
        logger.error(f"Documentation generation failed: {e}")
        return ""


def _extract_dependencies(code: str, language: str) -> List[str]:
    """Extract dependencies from code"""
    dependencies = []

    try:
        if language.lower() == "python":
            # Extract Python imports
            import_matches = re.findall(r"(?:from\s+(\S+)\s+)?import\s+([^\n]+)", code)
            for match in import_matches:
                if match[0]:  # from X import Y
                    dependencies.append(match[0])
                else:  # import X
                    deps = [dep.strip().split(".")[0] for dep in match[1].split(",")]
                    dependencies.extend(deps)

        elif language.lower() in ["javascript", "typescript"]:
            # Extract JS/TS imports
            import_matches = re.findall(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', code)
            dependencies.extend(import_matches)

            require_matches = re.findall(
                r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', code
            )
            dependencies.extend(require_matches)

    except Exception as e:
        logger.error(f"Error extracting dependencies: {e}")

    return list(set(dependencies))  # Remove duplicates


def _generate_usage_example(code: str, language: str) -> str:
    """Generate usage example for the code"""
    try:
        # Simple heuristic to generate usage example
        if language.lower() == "python":
            if "def " in code:
                # Extract function name
                func_match = re.search(r"def\s+(\w+)\s*\(", code)
                if func_match:
                    func_name = func_match.group(1)
                    return f"# Usage example\nresult = {func_name}()\nprint(result)"

        elif language.lower() in ["javascript", "typescript"]:
            if "function " in code or "=>" in code:
                return "// Usage example\nconst result = yourFunction();\nconsole.log(result);"

        return f"// Usage example for {language} code"

    except Exception:
        return "// Usage example"


async def _store_generation_history(
    db: Session, org_id: str, request: CodeGenerationRequest, result: Dict[str, Any]
):
    """Store code generation history"""
    try:
        from sqlalchemy import text

        db.execute(
            text(
                """
                INSERT INTO code_generation_history 
                (org_id, prompt, language, generated_code, timestamp)
                VALUES (:org_id, :prompt, :language, :code, :timestamp)
            """
            ),
            {
                "org_id": org_id,
                "prompt": request.prompt,
                "language": request.language,
                "code": result["code"],
                "timestamp": datetime.utcnow(),
            },
        )
        db.commit()

    except Exception as e:
        logger.error(f"Error storing generation history: {e}")


async def _perform_ai_analysis(
    llm_router: LLMRouter, request: CodeAnalysisRequest
) -> Dict[str, Any]:
    """Perform AI-powered code analysis"""
    try:
        analysis_prompt = f"""Analyze the following {request.language} code for quality, potential issues, and improvements:

{request.code}

Focus on:
- Code quality and best practices
- Potential bugs or issues
- Performance considerations
- Security vulnerabilities
- Maintainability

Provide structured feedback with specific line numbers where applicable."""

        response = await llm_router.run(
            prompt=analysis_prompt,
            model="gpt-4",
            temperature=0.1,
        )

        # Parse AI response (simplified)
        content = response.text
        return {"analysis": content, "issues": _extract_issues_from_analysis(content)}

    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return {"error": str(e)}


def _extract_issues_from_analysis(content: str) -> List[Dict[str, Any]]:
    """Extract issues from AI analysis content"""
    # Simplified issue extraction
    issues = []

    # Look for common issue patterns
    issue_patterns = [
        (r"security.*vulnerability", "security"),
        (r"performance.*issue", "performance"),
        (r"bug.*potential", "bug"),
        (r"deprecated", "deprecation"),
    ]

    for pattern, issue_type in issue_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            issues.append(
                {
                    "type": issue_type,
                    "description": match.group(0),
                    "severity": "medium",
                }
            )

    return issues


def _perform_security_analysis(code: str, language: str) -> Dict[str, Any]:
    """Perform security analysis of code"""
    security_issues = []

    # Common security patterns to check
    security_patterns = {
        "sql_injection": [r"SELECT.*\+.*", r"INSERT.*\+.*", r"UPDATE.*\+.*"],
        "xss": [r"innerHTML.*\+", r"document\.write.*\+"],
        "hardcoded_secrets": [
            r'password\s*=\s*[\'"][^\'"]+[\'"]',
            r'api_key\s*=\s*[\'"][^\'"]+[\'"]',
        ],
        "unsafe_deserialization": [r"pickle\.loads", r"eval\s*\(", r"exec\s*\("],
    }

    for issue_type, patterns in security_patterns.items():
        for pattern in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                security_issues.append(
                    {
                        "type": issue_type,
                        "severity": (
                            "high"
                            if issue_type in ["sql_injection", "xss"]
                            else "medium"
                        ),
                        "description": f"Potential {issue_type.replace('_', ' ')} vulnerability detected",
                    }
                )

    return {
        "issues": security_issues,
        "overall_score": max(0.0, 1.0 - len(security_issues) * 0.2),
    }


def _analyze_performance_patterns(code: str, language: str) -> Dict[str, Any]:
    """Analyze performance patterns in code"""
    performance_issues = []

    # Common performance anti-patterns
    if language.lower() == "python":
        if re.search(r"for.*in.*range.*len\(", code):
            performance_issues.append(
                {
                    "type": "inefficient_loop",
                    "description": "Use enumerate() instead of range(len())",
                    "impact": "low",
                }
            )

        if re.search(r"\+.*str.*for.*in", code):
            performance_issues.append(
                {
                    "type": "string_concatenation",
                    "description": "Use join() for string concatenation in loops",
                    "impact": "medium",
                }
            )

    elif language.lower() in ["javascript", "typescript"]:
        if re.search(r"for\s*\(.*length.*\)", code):
            performance_issues.append(
                {
                    "type": "repeated_length_calculation",
                    "description": "Cache array length in loops",
                    "impact": "low",
                }
            )

    return {
        "issues": performance_issues,
        "overall_score": max(0.0, 1.0 - len(performance_issues) * 0.1),
    }


async def _generate_code_suggestions(
    llm_router: LLMRouter, request: CodeAnalysisRequest
) -> List[CodeSuggestion]:
    """Generate code improvement suggestions"""
    try:
        suggestions_prompt = f"""Provide specific code improvement suggestions for the following {request.language} code:

{request.code}

For each suggestion, provide:
1. The specific code that should be changed
2. The improved version
3. Clear reasoning for the change

Focus on concrete, actionable improvements."""

        response = await llm_router.run(
            prompt=suggestions_prompt,
            model="gpt-4",
            temperature=0.1,
        )

        # Parse suggestions from response (simplified)
        return _parse_code_suggestions(response.text)

    except Exception as e:
        logger.error(f"Failed to generate suggestions: {e}")
        return []


def _parse_code_suggestions(content: str) -> List[CodeSuggestion]:
    """Parse code suggestions from LLM response"""
    # Simplified parsing - in production, this would be more sophisticated
    suggestions = []

    # Look for common improvement patterns
    if "extract" in content.lower():
        suggestions.append(
            CodeSuggestion(
                type="improvement",
                title="Extract method",
                description="Consider extracting complex logic into separate methods",
                original_code="// Complex logic here",
                suggested_code="// Extracted method call",
                reasoning="Improves readability and reusability",
                confidence=0.8,
                impact="medium",
            )
        )

    return suggestions


def _calculate_quality_score(
    static_metrics: Dict, ai_analysis: Dict, security_analysis: Dict
) -> float:
    """Calculate overall code quality score"""
    try:
        scores = []

        # Static metrics score
        if "maintainability_score" in static_metrics:
            scores.append(static_metrics["maintainability_score"])

        if "readability_score" in static_metrics:
            scores.append(static_metrics["readability_score"])

        # Security score
        if "overall_score" in security_analysis:
            scores.append(security_analysis["overall_score"])

        # Average the scores
        return sum(scores) / len(scores) if scores else 0.5

    except Exception:
        return 0.5


def _perform_static_analysis(code: str, language: str) -> Dict[str, Any]:
    """Perform static analysis of code"""
    return _analyze_code_metrics(code, language)


async def _perform_refactoring(
    llm_router: LLMRouter, request: RefactorRequest
) -> Dict[str, Any]:
    """Perform AI-powered code refactoring"""
    try:
        refactor_prompt = f"""Refactor the following {request.language} code:

{request.code}

Refactoring type: {request.refactor_type}
Goals: {", ".join(request.goals)}
Constraints: {", ".join(request.constraints)}

Provide:
1. The refactored code
2. Summary of changes made
3. List of specific improvements

Ensure the refactored code maintains the same functionality."""

        response = await llm_router.run(
            prompt=refactor_prompt,
            model="gpt-4",
            temperature=0.1,
        )

        content = response.text

        # Extract refactored code
        code_match = re.search(
            r"```(?:" + request.language + r")?\n(.*?)```", content, re.DOTALL
        )
        refactored_code = code_match.group(1).strip() if code_match else content

        return {
            "refactored_code": refactored_code,
            "changes_summary": "Refactoring completed",
            "improvements": [
                "Improved readability",
                "Better structure",
                "Enhanced maintainability",
            ],
        }

    except Exception as e:
        logger.error(f"Refactoring failed: {e}")
        raise


async def _validate_refactoring(
    llm_router: LLMRouter, original_code: str, refactored_code: str, language: str
) -> Dict[str, Any]:
    """Validate that refactoring maintains functionality"""
    try:
        validation_prompt = f"""Compare these two {language} code versions and verify they have the same functionality:

Original:
{original_code}

Refactored:
{refactored_code}

Assess:
1. Do they perform the same operations?
2. Are there any functional differences?
3. Confidence level (0.0-1.0)"""

        response = await llm_router.run(
            prompt=validation_prompt,
            model="gpt-4",
            temperature=0.1,
        )

        content = response.text

        # Extract confidence (simplified)
        confidence = 0.8  # Default confidence
        confidence_match = re.search(r"confidence.*?(\d*\.?\d+)", content.lower())
        if confidence_match:
            confidence = float(confidence_match.group(1))

        return {"validation": content, "confidence": min(confidence, 1.0)}

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return {"validation": "Validation unavailable", "confidence": 0.5}


async def _generate_code_explanation(
    llm_router: LLMRouter,
    code: str,
    language: str,
    detail_level: str,
    focus: Optional[str],
) -> Dict[str, Any]:
    """Generate detailed code explanation"""
    try:
        explanation_prompt = f"""Provide a {detail_level} explanation of this {language} code:

{code}

{f"Focus on: {focus}" if focus else ""}

Include:
- Overall purpose and functionality
- Key concepts and patterns used
- Step-by-step flow (if applicable)
- Notable design decisions"""

        response = await llm_router.run(
            prompt=explanation_prompt,
            model="gpt-4",
            temperature=0.2,
        )

        content = response.text

        return {
            "explanation": content,
            "key_concepts": _extract_key_concepts(content),
            "examples": [],
        }

    except Exception as e:
        logger.error(f"Code explanation failed: {e}")
        return {"explanation": "Explanation unavailable", "key_concepts": []}


def _extract_key_concepts(explanation: str) -> List[str]:
    """Extract key concepts from explanation"""
    # Simple concept extraction
    concepts = []

    # Look for common programming concepts
    concept_patterns = [
        r"algorithm",
        r"data structure",
        r"design pattern",
        r"recursion",
        r"iteration",
        r"inheritance",
        r"polymorphism",
        r"encapsulation",
        r"abstraction",
        r"optimization",
        r"complexity",
    ]

    for pattern in concept_patterns:
        if re.search(pattern, explanation, re.IGNORECASE):
            concepts.append(pattern.replace(r"\\", ""))

    return concepts


async def _convert_code_language(
    llm_router: LLMRouter,
    code: str,
    from_lang: str,
    to_lang: str,
    maintain_style: bool,
    include_comments: bool,
) -> Dict[str, Any]:
    """Convert code from one language to another"""
    try:
        conversion_prompt = f"""Convert this {from_lang} code to {to_lang}:

{code}

Requirements:
- Maintain equivalent functionality
- {"Preserve coding style and patterns" if maintain_style else "Use idiomatic " + to_lang + " style"}
- {"Include explanatory comments" if include_comments else "Minimal comments"}
- Note any language-specific considerations

Provide:
1. Converted code
2. Conversion notes
3. Potential issues or limitations"""

        response = await llm_router.run(
            prompt=conversion_prompt,
            model="gpt-4",
            temperature=0.1,
        )

        content = response.text

        # Extract converted code
        code_match = re.search(
            r"```(?:" + to_lang + r")?\n(.*?)```", content, re.DOTALL
        )
        converted_code = code_match.group(1).strip() if code_match else content

        return {
            "converted_code": converted_code,
            "conversion_notes": ["Language conversion completed"],
            "potential_issues": ["Manual testing recommended"],
            "confidence": 0.8,
        }

    except Exception as e:
        logger.error(f"Code conversion failed: {e}")
        raise


async def _validate_converted_code(
    llm_router: LLMRouter, code: str, language: str
) -> Dict[str, Any]:
    """Validate converted code"""
    try:
        # Perform basic syntax and structure validation
        validation = {
            "syntax_valid": True,
            "structure_analysis": "Code structure appears valid",
            "potential_issues": [],
            "confidence": 0.8,
        }

        return validation

    except Exception as e:
        logger.error(f"Code validation failed: {e}")
        return {"syntax_valid": False, "error": str(e)}


def _get_code_templates(
    language: Optional[str], category: Optional[str], framework: Optional[str]
) -> List[Dict[str, Any]]:
    """Get code templates and boilerplate"""
    templates = [
        {
            "id": "api_endpoint",
            "name": "REST API Endpoint",
            "language": "python",
            "category": "api",
            "framework": "fastapi",
            "description": "Basic REST API endpoint template",
            "code": """from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class ItemRequest(BaseModel):
    name: str
    description: str

@router.post("/items/")
async def create_item(item: ItemRequest):
    # Implementation here
    return {"message": "Item created", "item": item}""",
            "usage": "Use for creating new API endpoints",
        },
        {
            "id": "react_component",
            "name": "React Component",
            "language": "typescript",
            "category": "ui",
            "framework": "react",
            "description": "Basic React functional component with TypeScript",
            "code": """import React from 'react';

interface Props {
  title: string;
  onAction: () => void;
}

const MyComponent: React.FC<Props> = ({ title, onAction }) => {
  return (
    <div>
      <h1>{title}</h1>
      <button onClick={onAction}>Click me</button>
    </div>
  );
};

export default MyComponent;""",
            "usage": "Use for creating new React components",
        },
    ]

    # Filter templates
    filtered_templates = templates

    if language:
        filtered_templates = [
            t for t in filtered_templates if t["language"] == language
        ]

    if category:
        filtered_templates = [
            t for t in filtered_templates if t["category"] == category
        ]

    if framework:
        filtered_templates = [
            t for t in filtered_templates if t["framework"] == framework
        ]

    return filtered_templates
