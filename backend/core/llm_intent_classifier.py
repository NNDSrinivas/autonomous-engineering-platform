"""
LLM-Based Intent Classifier for NAVI
Truly dynamic intent classification using LLM instead of hardcoded regex patterns

Supports multiple LLM providers:
- OpenAI (GPT-4, GPT-4o-mini, etc.)
- Anthropic (Claude 3.7 Opus, Claude 3.5 Sonnet, etc.)
- Google (Gemini Pro, etc.)
- Mistral, xAI, and more
"""

import json
import os
from typing import Dict, Any, List
from dataclasses import dataclass
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class IntentClassification:
    """Result of intent classification"""

    action: str
    target: str
    confidence: float
    reasoning: str
    original_message: str


class LLMIntentClassifier:
    """
    Intelligent intent classifier using LLM.
    No regex patterns - understands natural language variations.
    Supports multiple LLM providers via the professional LLM router.
    """

    def __init__(self, config_loader=None, model_provider="openai", model_name=None):
        """
        Initialize with optional config loader for action examples

        Args:
            config_loader: Optional config loader for examples
            model_provider: "openai", "anthropic", "google", "mistral", etc. (default: "openai")
            model_name: Specific model to use (e.g., "gpt-4o-mini", "claude-3-5-sonnet-20241022")
        """
        self.config_loader = config_loader
        self.examples = (
            self._load_examples() if config_loader else self._get_default_examples()
        )
        self.model_provider = model_provider
        self.model_name = model_name or self._get_default_model(model_provider)

        # Initialize professional LLM router
        try:
            from backend.ai.llm_router import LLMRouter

            self.llm_router = LLMRouter()
            self.has_router = True
            logger.info(
                f"✅ Professional LLM router initialized (provider: {model_provider}, model: {self.model_name})"
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize professional LLM router: {e}")
            self.llm_router = None
            self.has_router = False

        # Fallback: Check for API keys for legacy OpenAI support
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

        if not self.has_router:
            if model_provider == "openai" and not self.openai_api_key:
                logger.warning(
                    "⚠️ OPENAI_API_KEY not set, OpenAI LLM classification will fail"
                )
            elif model_provider == "anthropic" and not self.anthropic_api_key:
                logger.warning(
                    "⚠️ ANTHROPIC_API_KEY not set, Anthropic LLM classification will fail"
                )

    def _get_default_model(self, provider: str) -> str:
        """
        Get default model for provider.

        Uses cheaper/faster models for intent classification since this is called
        frequently (potentially once per user message). Can be overridden via
        NAVI_LLM_MODEL environment variable for higher accuracy if needed.
        """
        defaults = {
            "openai": "gpt-4o-mini",  # Fast and cheap for frequent classification
            "anthropic": "claude-3-5-sonnet-20241022",
            "google": "gemini-1.5-pro",
            "mistral": "mistral-large-latest",
            "xai": "grok-2",
            "local": "llama3",
        }
        return defaults.get(provider, "claude-3-5-sonnet-20241022")

    def _get_default_examples(self) -> Dict[str, List[str]]:
        """Default examples if config not available"""
        return {
            "open_project": [
                "open my-app",
                "switch to dashboard project",
                "go to marketing-website",
                "load the blog project",
            ],
            "create_component": [
                "create a button component",
                "make me a sidebar component",
                "I need a navbar component",
                "build a login form component",
                "add a footer component",
                "can you create a header component?",
            ],
            "create_page": [
                "create a login page",
                "make a dashboard page",
                "I want a settings screen",
                "build me a profile page",
                "add an about page",
            ],
            "create_api": [
                "create an API for users",
                "make an endpoint for authentication",
                "add a REST API for products",
            ],
            "install_package": [
                "install axios",
                "add react-router to my project",
                "I need lodash",
                "install express as a dependency",
            ],
            "git_commit": [
                "commit these changes",
                "commit with message 'added navbar'",
                "make a commit",
            ],
            "git_push": ["push to origin", "push my changes", "upload to github"],
            "create_pr": [
                "create a pull request",
                "make a PR",
                "open a pull request for review",
            ],
            "fix_bug": [
                "fix the login bug",
                "debug the authentication issue",
                "solve the navbar problem",
            ],
            "refactor": [
                "refactor the auth module",
                "clean up this code",
                "improve the component structure",
            ],
            "explain_code": [
                "explain this function",
                "what does this code do?",
                "describe how authentication works",
            ],
        }

    def _load_examples(self) -> Dict[str, List[str]]:
        """Load examples from config if available"""
        try:
            patterns = self.config_loader.load_intent_patterns("english")
            examples_dict = {}
            for pattern in patterns:
                if pattern.examples:
                    examples_dict[pattern.action] = pattern.examples
            return examples_dict if examples_dict else self._get_default_examples()
        except Exception as e:
            logger.warning(f"Failed to load examples from config: {e}")
            return self._get_default_examples()

    def _build_classification_prompt(self, message: str) -> str:
        """Build the LLM prompt for intent classification"""

        # Format examples for the prompt
        examples_text = ""
        for action, examples in self.examples.items():
            examples_text += f"\n**{action}:**\n"
            for example in examples[:3]:  # Show top 3 examples per action
                examples_text += f'  - "{example}"\n'

        prompt = f"""You are an intelligent coding assistant that classifies user intents.

Your job: Classify the user's message into ONE of these actions and extract the target entity.

Available Actions:
- open_project: User wants to open/switch to a different project
- create_component: User wants to create a UI component (Button, Navbar, Sidebar, etc.)
- create_page: User wants to create a page/screen/route
- create_api: User wants to create an API endpoint
- create_file: User wants to create a generic file
- install_package: User wants to install a package/dependency
- git_commit: User wants to commit changes
- git_push: User wants to push to remote
- git_branch: User wants to create a branch
- create_pr: User wants to create a pull request
- fix_bug: User wants to fix a bug or issue
- refactor: User wants to refactor/improve code
- create_test: User wants to create tests
- run_tests: User wants to run tests
- explain_code: User wants explanation of code
- add_feature: User wants to add a new feature
- general: None of the above (conversational or unclear)

Example Classifications:
{examples_text}

User Message: "{message}"

Analyze the message and respond with ONLY valid JSON (no markdown):
{{
  "action": "the_action_name",
  "target": "what the user wants to create/modify (empty string if N/A)",
  "confidence": 0.95,
  "reasoning": "brief explanation of why you chose this classification"
}}

Rules:
- confidence: 0.9-1.0 for very clear intent, 0.7-0.9 for somewhat clear, 0.5-0.7 for unclear
- target: extract the specific entity name (component name, package name, etc.)
- If message is conversational/greeting/unclear, use "general" action
- Be flexible with phrasing - understand natural variations

JSON Response:"""

        return prompt

    async def classify(self, message: str) -> IntentClassification:
        """
        Classify user intent using LLM.

        Args:
            message: User's natural language message

        Returns:
            IntentClassification with action, target, confidence, reasoning
        """
        # Try professional LLM router first
        if self.has_router and self.llm_router:
            try:
                return await self._classify_with_router(message)
            except Exception as e:
                logger.warning(f"Professional LLM router failed, falling back: {e}")

        # Fallback to legacy OpenAI support
        if not self.openai_api_key:
            logger.error("Cannot classify: No LLM provider available")
            return IntentClassification(
                action="general",
                target=message,
                confidence=0.5,
                reasoning="LLM not available (no API key)",
                original_message=message,
            )

        try:
            import openai

            # Use OpenAI API for classification
            client = openai.OpenAI(api_key=self.openai_api_key)

            prompt = self._build_classification_prompt(message)

            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cheap model for classification
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise intent classifier. Always respond with valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=150,
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON response
            # Remove markdown code blocks if present
            if result_text.startswith("```json"):
                result_text = (
                    result_text.replace("```json", "").replace("```", "").strip()
                )
            elif result_text.startswith("```"):
                result_text = result_text.replace("```", "").strip()

            result = json.loads(result_text)

            classification = IntentClassification(
                action=result.get("action", "general"),
                target=result.get("target", ""),
                confidence=float(result.get("confidence", 0.8)),
                reasoning=result.get("reasoning", "Classified by LLM"),
                original_message=message,
            )

            logger.info(
                f"🤖 LLM classified: '{message}' → action={classification.action}, "
                f"target={classification.target}, confidence={classification.confidence}"
            )

            return classification

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse LLM response as JSON: {e}, response: {result_text}"
            )
            return self._fallback_classification(message)

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return self._fallback_classification(message)

    async def _classify_with_router(self, message: str) -> IntentClassification:
        """
        Classify using the professional multi-provider LLM router.

        Args:
            message: User's natural language message

        Returns:
            IntentClassification with action, target, confidence, reasoning
        """
        prompt = self._build_classification_prompt(message)

        # Call professional LLM router
        response = await self.llm_router.run(
            prompt=prompt,
            system_prompt="You are a precise intent classifier. Always respond with valid JSON only.",
            model=self.model_name,
            provider=self.model_provider,
            temperature=0.1,  # Low temperature for consistent classification
            max_tokens=200,
        )

        result_text = response.text.strip()

        # Parse JSON response
        # Remove markdown code blocks if present
        if result_text.startswith("```json"):
            result_text = result_text.replace("```json", "").replace("```", "").strip()
        elif result_text.startswith("```"):
            result_text = result_text.replace("```", "").strip()

        result = json.loads(result_text)

        classification = IntentClassification(
            action=result.get("action", "general"),
            target=result.get("target", ""),
            confidence=float(result.get("confidence", 0.8)),
            reasoning=result.get(
                "reasoning", f"Classified by {self.model_provider}:{self.model_name}"
            ),
            original_message=message,
        )

        logger.info(
            f"🤖 {self.model_provider}:{self.model_name} classified: '{message}' → "
            f"action={classification.action}, target={classification.target}, "
            f"confidence={classification.confidence:.2f}"
        )

        return classification

    def _fallback_classification(self, message: str) -> IntentClassification:
        """Fallback classification using simple keyword matching"""
        message_lower = message.lower()

        # Simple keyword-based fallback
        if any(word in message_lower for word in ["open", "switch", "go to", "load"]):
            words = message.split()
            target = words[-1] if words else message
            return IntentClassification(
                action="open_project",
                target=target,
                confidence=0.6,
                reasoning="Fallback: keyword matching",
                original_message=message,
            )
        elif any(word in message_lower for word in ["create", "make", "add", "build"]):
            if "component" in message_lower:
                # Extract component name (words before "component")
                words = message_lower.split()
                if "component" in words:
                    idx = words.index("component")
                    if idx > 0:
                        target = words[idx - 1]
                    else:
                        target = "unknown"
                else:
                    target = "unknown"
                return IntentClassification(
                    action="create_component",
                    target=target,
                    confidence=0.6,
                    reasoning="Fallback: keyword matching",
                    original_message=message,
                )
            elif "page" in message_lower or "screen" in message_lower:
                words = message_lower.split()
                if "page" in words:
                    idx = words.index("page")
                    if idx > 0:
                        target = words[idx - 1]
                    else:
                        target = "unknown"
                else:
                    target = "unknown"
                return IntentClassification(
                    action="create_page",
                    target=target,
                    confidence=0.6,
                    reasoning="Fallback: keyword matching",
                    original_message=message,
                )
        elif "install" in message_lower or "add" in message_lower:
            words = message.split()
            target = words[-1] if words else message
            return IntentClassification(
                action="install_package",
                target=target,
                confidence=0.6,
                reasoning="Fallback: keyword matching",
                original_message=message,
            )

        # General fallback
        return IntentClassification(
            action="general",
            target=message,
            confidence=0.5,
            reasoning="Fallback: no clear intent detected",
            original_message=message,
        )

    def classify_sync(self, message: str) -> Dict[str, Any]:
        """
        Synchronous wrapper for classify() - for backward compatibility.
        Note: This uses a simple fallback as sync LLM calls are not ideal.
        """

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        classification = loop.run_until_complete(self.classify(message))

        return {
            "action": classification.action,
            "target": classification.target,
            "original": classification.original_message,
            "confidence": classification.confidence,
        }


# Singleton instance
_classifier_instance = None


def get_llm_classifier():
    """
    Get singleton LLM classifier instance.

    Configuration via environment variables:
    - NAVI_LLM_PROVIDER: openai, anthropic, google, mistral, xai (default: openai)
    - NAVI_LLM_MODEL: specific model name (default: provider-specific)
    """
    global _classifier_instance
    if _classifier_instance is None:
        # Get provider and model from environment
        provider = os.getenv("NAVI_LLM_PROVIDER", "openai").lower()
        model = os.getenv("NAVI_LLM_MODEL")

        try:
            from backend.core.config_loader import get_config_loader

            config_loader = get_config_loader()
            _classifier_instance = LLMIntentClassifier(
                config_loader=config_loader, model_provider=provider, model_name=model
            )
            logger.info(
                f"✅ LLM Intent Classifier initialized with {provider}:{model or 'default'}"
            )
        except Exception as e:
            logger.warning(f"Failed to load config, using default examples: {e}")
            _classifier_instance = LLMIntentClassifier(
                model_provider=provider, model_name=model
            )
    return _classifier_instance
