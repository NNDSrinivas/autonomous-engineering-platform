import json
import logging
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import openai

from .config import settings

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        # Configure OpenAI with API key from settings
        self.client = None
        if (
            settings.openai_api_key
            and settings.openai_api_key != "your-openai-api-key-here"
        ):
            try:
                self.client = openai.OpenAI(api_key=settings.openai_api_key)
                logger.info("AIService initialized with OpenAI API")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")
                self.client = None
        else:
            logger.warning(
                "OpenAI API key not configured. AI features will use mock responses."
            )

        logger.info("AIService initialized")

    async def ask_question(
        self, question: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a question using AI and return a comprehensive response
        """
        try:
            logger.info(f"Processing question: {question[:50]}...")

            if self.client:
                # Real AI processing with OpenAI
                messages = [
                    {
                        "role": "system",
                        "content": """You are an expert engineering assistant specializing in software development, architecture, and best practices.
                        Provide detailed, actionable answers with code examples when relevant.
                        Consider the provided context to make your response more relevant.""",
                    },
                    {
                        "role": "user",
                        "content": f"Question: {question}\n\nContext: {json.dumps(context) if context else 'No additional context'}",
                    },
                ]

                response = await self._call_openai(messages)

                return {
                    "answer": response,
                    "confidence": 0.95,
                    "sources": ["OpenAI GPT-4"],
                    "context_used": context or {},
                    "ai_powered": True,
                }
            else:
                # Mock response when API key not available
                mock_answers = {
                    "async": "Async programming in Python allows code to run concurrently using async/await syntax. Unlike synchronous code that blocks execution, async code can handle multiple operations simultaneously, making it ideal for I/O operations like API calls or database queries.",
                    "performance": "Code performance can be optimized through algorithmic improvements, caching, efficient data structures, and proper resource management. Profile your code first to identify bottlenecks.",
                    "api": "Good API design follows REST principles: use proper HTTP methods, meaningful URLs, consistent response formats, proper status codes, and comprehensive documentation.",
                    "testing": "Effective testing includes unit tests for individual functions, integration tests for component interactions, and end-to-end tests for complete workflows. Aim for high coverage and meaningful assertions.",
                    "default": f"To properly answer '{question}', I would need access to OpenAI's API. This is a mock response demonstrating the system's capability.",
                }

                # Simple keyword matching for demo
                answer_key = "default"
                for key in mock_answers.keys():
                    if key in question.lower():
                        answer_key = key
                        break

                return {
                    "answer": mock_answers[answer_key],
                    "confidence": 0.75,
                    "sources": ["Engineering Best Practices Database"],
                    "context_used": context or {},
                    "ai_powered": False,
                    "note": "Add your OpenAI API key to enable full AI capabilities",
                }

        except Exception as e:
            logger.error(f"Error processing question: {e}")
            return {
                "answer": "I apologize, but I encountered an error processing your question.",
                "confidence": 0.0,
                "sources": [],
                "error": str(e),
                "ai_powered": False,
            }

    async def analyze_code(
        self, code: str, language: str, analysis_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Analyze code and provide insights
        """
        try:
            logger.info(f"Analyzing {language} code ({analysis_type})")

            if self.client:
                # Real AI code analysis
                prompt = f"""Analyze this {language} code for {analysis_type} aspects:

```{language}
{code}
```

Provide analysis in this JSON format:
{{
    "issues": ["list of issues found"],
    "suggestions": ["list of improvement suggestions"],
    "complexity_score": 1-10,
    "maintainability_score": 1-10,
    "security_concerns": ["list of security issues"],
    "performance_notes": ["performance optimization suggestions"]
}}"""

                messages = [
                    {
                        "role": "system",
                        "content": "You are an expert code reviewer. Analyze code thoroughly and provide constructive feedback.",
                    },
                    {"role": "user", "content": prompt},
                ]

                response = await self._call_openai(messages)

                try:
                    # Try to parse AI response as JSON
                    analysis = json.loads(response)
                    analysis.update(
                        {
                            "language": language,
                            "analysis_type": analysis_type,
                            "ai_powered": True,
                        }
                    )
                    return analysis
                except json.JSONDecodeError:
                    # Fallback if AI doesn't return valid JSON
                    return {
                        "language": language,
                        "analysis_type": analysis_type,
                        "raw_analysis": response,
                        "ai_powered": True,
                    }
            else:
                # Mock code analysis
                mock_analysis = {
                    "python": {
                        "issues": [
                            "Recursive implementation may cause stack overflow for large inputs"
                        ],
                        "suggestions": [
                            "Consider using dynamic programming or iterative approach",
                            "Add input validation",
                        ],
                        "complexity_score": 8,
                        "maintainability_score": 6,
                        "security_concerns": ["No input sanitization"],
                        "performance_notes": [
                            "O(2^n) time complexity - consider memoization"
                        ],
                    },
                    "javascript": {
                        "issues": ["No error handling", "Variable scope concerns"],
                        "suggestions": [
                            "Add try-catch blocks",
                            "Use const/let instead of var",
                        ],
                        "complexity_score": 5,
                        "maintainability_score": 7,
                        "security_concerns": ["Potential XSS if handling user input"],
                        "performance_notes": [
                            "Consider async/await for better performance"
                        ],
                    },
                }

                analysis = mock_analysis.get(
                    language.lower(),
                    {
                        "issues": [
                            "Language-specific analysis not available in demo mode"
                        ],
                        "suggestions": [
                            "Enable AI features with OpenAI API key for detailed analysis"
                        ],
                        "complexity_score": 5,
                        "maintainability_score": 5,
                        "security_concerns": [],
                        "performance_notes": [],
                    },
                )

                analysis.update(
                    {
                        "language": language,
                        "analysis_type": analysis_type,
                        "ai_powered": False,
                        "note": "Add your OpenAI API key to enable full AI-powered code analysis",
                    }
                )

                return analysis

        except Exception as e:
            logger.error(f"Error analyzing code: {e}")
            return {
                "error": str(e),
                "language": language,
                "analysis_type": analysis_type,
                "ai_powered": False,
            }

    async def _call_openai(self, messages: List[Dict[str, str]]) -> str:
        """
        Make a call to OpenAI API
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4", messages=messages, temperature=0.7, max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise e
