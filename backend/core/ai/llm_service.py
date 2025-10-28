"""
Engineering-focused LLM service for autonomous platform
Provides AI assistance tailored for software engineering teams
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from openai import OpenAI
import structlog

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class EngineeringResponse:
    """Response from engineering AI assistant"""

    answer: str
    reasoning: str
    suggested_actions: List[str]
    confidence: float
    code_suggestions: Optional[List[str]] = None
    technical_depth: str = "intermediate"  # basic, intermediate, advanced


@dataclass
class CodeAnalysis:
    """Code analysis result"""

    quality_score: float  # 0.0 to 1.0
    issues: List[Dict[str, Any]]
    suggestions: List[str]
    complexity: Dict[str, Any]
    test_suggestions: List[str]
    security_concerns: List[str] = None


class LLMService:
    """
    Engineering-focused Language Model service
    Specialized for software development teams and autonomous coding
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()

        if not self.settings.openai_api_key:
            raise ValueError("OpenAI API key is required for LLM service")

        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.model = self.settings.openai_model

        logger.info("LLM Service initialized for engineering platform", model=self.model)

    async def generate_engineering_response(
        self, question: str, context: Dict[str, Any]
    ) -> EngineeringResponse:
        """Generate engineering-focused response with team context"""

        system_prompt = self._build_engineering_system_prompt(context)
        user_prompt = self._build_user_prompt(question, context)

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
            )

            content = response.choices[0].message.content

            # Parse structured response
            return self._parse_engineering_response(content)

        except Exception as e:
            logger.error("Error generating engineering response", error=str(e))
            return EngineeringResponse(
                answer="I encountered an error processing your request. Please try again.",
                reasoning="Technical error occurred",
                suggested_actions=[
                    "Try rephrasing your question",
                    "Check system status",
                ],
                confidence=0.1,
            )

    async def analyze_code(self, code: str, language: str, context: Dict[str, Any]) -> CodeAnalysis:
        """Analyze code and provide engineering insights"""

        system_prompt = """You are an expert software engineer and code reviewer. 
        Analyze the provided code and return a structured assessment including:
        - Quality score (0.0 to 1.0)
        - Specific issues found
        - Improvement suggestions
        - Complexity analysis
        - Test recommendations
        - Security concerns if any
        
        Be thorough but constructive in your analysis."""

        user_prompt = f"""
        Please analyze this {language} code:
        
        ```{language}
        {code}
        ```
        
        Context: {context.get("description", "No additional context provided")}
        Project: {context.get("project", "Unknown")}
        
        Provide detailed analysis focusing on:
        1. Code quality and maintainability
        2. Performance considerations
        3. Security implications
        4. Testing recommendations
        5. Architecture alignment
        """

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,  # Lower temperature for code analysis
                max_tokens=2000,
            )

            content = response.choices[0].message.content

            # Parse analysis response
            return self._parse_code_analysis(content)

        except Exception as e:
            logger.error("Error analyzing code", error=str(e))
            return CodeAnalysis(
                quality_score=0.5,
                issues=[{"type": "analysis_error", "message": "Could not analyze code"}],
                suggestions=["Manual code review recommended"],
                complexity={"cyclomatic": "unknown"},
                test_suggestions=["Add basic unit tests"],
            )

    async def generate_code_suggestion(
        self, description: str, language: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate code suggestions based on description"""

        system_prompt = """You are an expert software engineer specializing in code generation.
        Generate clean, well-documented, production-ready code based on requirements.
        Include proper error handling, type hints (where applicable), and follow best practices."""

        user_prompt = f"""
        Generate {language} code for: {description}
        
        Context:
        - Project: {context.get("project", "Unknown")}
        - Framework: {context.get("framework", "Standard")}
        - Style: {context.get("coding_style", "Standard best practices")}
        
        Requirements:
        1. Follow {language} best practices
        2. Include comprehensive documentation
        3. Add appropriate error handling
        4. Consider testing implications
        5. Ensure maintainability
        """

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=2500,
            )

            content = response.choices[0].message.content

            return {
                "code": content,
                "language": language,
                "description": description,
                "generated_at": "2025-10-11T00:00:00Z",
            }

        except Exception as e:
            logger.error("Error generating code suggestion", error=str(e))
            return {
                "code": "# Error generating code. Please try again later.",
                "language": language,
                "description": description,
                "error": "code_generation_failed",
            }

    def _build_engineering_system_prompt(self, context: Dict[str, Any]) -> str:
        """Build system prompt for engineering contexts"""

        base_prompt = """You are an AI engineering assistant and digital coworker for software development teams.
        
        Your role is to:
        1. Provide technical guidance and solutions
        2. Help with code reviews and architecture decisions  
        3. Assist with debugging and problem-solving
        4. Support team collaboration and knowledge sharing
        5. Offer best practices and industry insights
        
        You have access to team context, project history, and codebase knowledge.
        Always consider:
        - Team's technical stack and preferences
        - Project constraints and requirements
        - Code quality and maintainability
        - Performance and scalability
        - Security implications
        
        Provide practical, actionable advice that helps the team move forward efficiently."""

        # Add specific context
        if context.get("project"):
            base_prompt += f"\n\nCurrent project: {context['project']}"

        if context.get("team_members"):
            base_prompt += f"\nTeam members: {', '.join(context['team_members'])}"

        if context.get("tech_stack"):
            base_prompt += f"\nTech stack: {', '.join(context['tech_stack'])}"

        return base_prompt

    def _build_user_prompt(self, question: str, context: Dict[str, Any]) -> str:
        """Build user prompt with relevant context"""

        prompt = f"Question: {question}\n\n"

        # Add relevant context
        if context.get("relevant_knowledge"):
            prompt += "Relevant context from team knowledge:\n"
            for doc in context["relevant_knowledge"][:3]:  # Limit context
                prompt += f"- {doc.get('content', '')}\n"
            prompt += "\n"

        if context.get("current_files"):
            prompt += f"Currently working on files: {', '.join(context['current_files'])}\n\n"

        if context.get("recent_changes"):
            prompt += f"Recent changes: {context['recent_changes']}\n\n"

        return prompt

    def _parse_engineering_response(self, content: str) -> EngineeringResponse:
        """Parse LLM response into structured engineering response"""

        # Simple parsing - in production, could use more sophisticated parsing
        lines = content.split("\n")

        answer = content  # Full content as answer
        reasoning = "AI analysis based on engineering best practices"
        suggested_actions = []
        confidence = 0.8

        # Extract suggested actions if formatted properly
        action_section = False
        for line in lines:
            if "suggested actions" in line.lower() or "recommendations" in line.lower():
                action_section = True
                continue
            if action_section and line.strip().startswith(("-", "*", "1.", "2.")):
                suggested_actions.append(line.strip().lstrip("-*0123456789. "))

        if not suggested_actions:
            suggested_actions = ["Review the provided guidance", "Apply best practices"]

        return EngineeringResponse(
            answer=answer,
            reasoning=reasoning,
            suggested_actions=suggested_actions,
            confidence=confidence,
        )

    def _parse_code_analysis(self, content: str) -> CodeAnalysis:
        """Parse code analysis response into structured format"""

        # Default values
        quality_score = 0.7
        issues = []
        suggestions = []
        complexity = {"analysis": "completed"}
        test_suggestions = []

        # Simple parsing - could be enhanced with structured output
        lines = content.split("\n")

        current_section = None
        for line in lines:
            line = line.strip()

            if "quality score" in line.lower():
                # Try to extract score
                words = line.split()
                for word in words:
                    try:
                        score = float(word.replace("%", "")) / 100 if "%" in word else float(word)
                        if 0 <= score <= 1:
                            quality_score = score
                            break
                    except ValueError:
                        continue

            elif "issues" in line.lower():
                current_section = "issues"
            elif "suggestions" in line.lower() or "recommendations" in line.lower():
                current_section = "suggestions"
            elif "test" in line.lower():
                current_section = "tests"
            elif line.startswith(("-", "*", "1.", "2.")) and current_section:
                clean_line = line.lstrip("-*0123456789. ")
                if current_section == "issues":
                    issues.append({"type": "code_issue", "message": clean_line})
                elif current_section == "suggestions":
                    suggestions.append(clean_line)
                elif current_section == "tests":
                    test_suggestions.append(clean_line)

        # Ensure we have some default values
        if not suggestions:
            suggestions = [
                "Consider adding more documentation",
                "Review for potential optimizations",
            ]

        if not test_suggestions:
            test_suggestions = [
                "Add unit tests for critical functions",
                "Consider integration tests",
            ]

        return CodeAnalysis(
            quality_score=quality_score,
            issues=issues,
            suggestions=suggestions,
            complexity=complexity,
            test_suggestions=test_suggestions,
        )
