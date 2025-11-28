"""
Provider Configuration API Routes
================================

FastAPI endpoints for managing LLM provider configurations (BYOK).

Endpoints:
- GET /api/providers - List configured providers
- POST /api/providers - Add/update provider configuration  
- DELETE /api/providers/{provider_id} - Remove provider configuration
- GET /api/providers/models - List models for configured providers
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field, SecretStr
from typing import Any, Dict, List, Optional
import logging
from sqlalchemy.orm import Session

from ...database.session import get_db
from ..deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/providers", tags=["providers"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class ProviderConfigRequest(BaseModel):
    """Request model for provider configuration."""
    
    provider_id: str = Field(..., description="Provider identifier (e.g., 'openai', 'anthropic')")
    display_name: Optional[str] = Field(None, description="Custom display name")
    
    # Authentication
    api_key: SecretStr = Field(..., description="API key for the provider")
    org_id: Optional[str] = Field(None, description="Organization ID (OpenAI only)")
    base_url: Optional[str] = Field(None, description="Custom base URL (for self-hosted)")
    
    # Preferences
    default_model: Optional[str] = Field(None, description="Default model for this provider")
    enabled: bool = Field(True, description="Whether this provider is enabled")
    priority: int = Field(50, description="Priority for SMART-AUTO selection (lower = higher priority)")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Tags for organization")
    notes: Optional[str] = Field(None, description="Notes about this configuration")


class ProviderConfigResponse(BaseModel):
    """Response model for provider configuration."""
    
    id: str
    provider_id: str
    display_name: str
    base_url: Optional[str]
    default_model: Optional[str]
    enabled: bool
    priority: int
    tags: List[str]
    notes: Optional[str]
    
    # Metadata
    created_at: str
    updated_at: str
    user_id: str
    
    # Status
    api_key_set: bool = Field(..., description="Whether API key is configured (without revealing it)")
    last_validated: Optional[str] = Field(None, description="When the API key was last validated")
    validation_status: Optional[str] = Field(None, description="'valid', 'invalid', or 'unknown'")


class ValidateProviderRequest(BaseModel):
    """Request to validate a provider configuration."""
    
    provider_id: str
    api_key: SecretStr
    org_id: Optional[str] = None
    base_url: Optional[str] = None
    test_model: Optional[str] = Field(None, description="Model to test with")


class ValidateProviderResponse(BaseModel):
    """Response for provider validation."""
    
    provider_id: str
    valid: bool
    error: Optional[str] = None
    available_models: List[str] = Field(default_factory=list)
    test_response: Optional[str] = Field(None, description="Sample response from test call")
    latency_ms: Optional[float] = None


# ---------------------------------------------------------------------------
# In-Memory Storage (for development)
# ---------------------------------------------------------------------------

# TODO: Replace with proper database storage
_provider_configs: Dict[str, Dict[str, Any]] = {}


def _get_user_providers(user_id: str) -> Dict[str, Dict[str, Any]]:
    """Get all provider configurations for a user."""
    return _provider_configs.get(user_id, {})


def _save_user_provider(user_id: str, provider_id: str, config: Dict[str, Any]) -> None:
    """Save a provider configuration for a user."""
    if user_id not in _provider_configs:
        _provider_configs[user_id] = {}
    _provider_configs[user_id][provider_id] = config


def _delete_user_provider(user_id: str, provider_id: str) -> bool:
    """Delete a provider configuration for a user."""
    if user_id in _provider_configs and provider_id in _provider_configs[user_id]:
        del _provider_configs[user_id][provider_id]
        return True
    return False


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[ProviderConfigResponse])
async def list_provider_configurations(
    current_user: Any = Depends(get_current_user),
) -> List[ProviderConfigResponse]:
    """
    List all configured LLM providers for the current user.
    """
    
    user_id = current_user["user_id"]
    user_providers = _get_user_providers(user_id)
    
    configurations = []
    
    for provider_id, config in user_providers.items():
        configurations.append(ProviderConfigResponse(
            id=f"{user_id}_{provider_id}",
            provider_id=provider_id,
            display_name=config.get("display_name", provider_id.title()),
            base_url=config.get("base_url"),
            default_model=config.get("default_model"),
            enabled=config.get("enabled", True),
            priority=config.get("priority", 50),
            tags=config.get("tags", []),
            notes=config.get("notes"),
            created_at=config.get("created_at", "2024-01-01T00:00:00Z"),
            updated_at=config.get("updated_at", "2024-01-01T00:00:00Z"),
            user_id=user_id,
            api_key_set=bool(config.get("api_key")),
            last_validated=config.get("last_validated"),
            validation_status=config.get("validation_status", "unknown"),
        ))
    
    # Sort by priority (lower number = higher priority)
    configurations.sort(key=lambda x: x.priority)
    
    return configurations


@router.post("/", response_model=ProviderConfigResponse)
async def create_or_update_provider_configuration(
    request: ProviderConfigRequest,
    current_user: Any = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> ProviderConfigResponse:
    """
    Create or update a provider configuration with BYOK.
    """
    
    user_id = current_user["user_id"]
    
    # Validate provider_id against registry
    try:
        from ...ai.llm_model_registry import get_provider
        registry_provider = get_provider(request.provider_id)
        if not registry_provider:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown provider '{request.provider_id}'. Check available providers."
            )
    except ImportError:
        logger.warning("Could not validate provider against registry")
    
    # Store configuration
    import datetime
    now = datetime.datetime.utcnow().isoformat() + "Z"
    
    config = {
        "provider_id": request.provider_id,
        "display_name": request.display_name or request.provider_id.title(),
        "api_key": request.api_key.get_secret_value(),
        "org_id": request.org_id,
        "base_url": request.base_url,
        "default_model": request.default_model,
        "enabled": request.enabled,
        "priority": request.priority,
        "tags": request.tags,
        "notes": request.notes,
        "updated_at": now,
    }
    
    # Set created_at for new configurations
    existing = _get_user_providers(user_id).get(request.provider_id)
    if not existing:
        config["created_at"] = now
    else:
        config["created_at"] = existing.get("created_at", now)
    
    _save_user_provider(user_id, request.provider_id, config)
    
    # Schedule background validation
    background_tasks.add_task(
        _validate_provider_background,
        user_id,
        request.provider_id,
        config["api_key"],
        request.org_id,
        request.base_url,
    )
    
    logger.info(f"[API] Configured provider {request.provider_id} for user {user_id}")
    
    return ProviderConfigResponse(
        id=f"{user_id}_{request.provider_id}",
        provider_id=request.provider_id,
        display_name=config["display_name"],
        base_url=config["base_url"],
        default_model=config["default_model"],
        enabled=config["enabled"],
        priority=config["priority"],
        tags=config["tags"],
        notes=config["notes"],
        created_at=config["created_at"],
        updated_at=config["updated_at"],
        user_id=user_id,
        api_key_set=True,
        validation_status="validating",
    )


@router.delete("/{provider_id}")
async def delete_provider_configuration(
    provider_id: str,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Delete a provider configuration.
    """
    
    user_id = current_user["user_id"]
    
    if not _delete_user_provider(user_id, provider_id):
        raise HTTPException(
            status_code=404,
            detail=f"Provider configuration '{provider_id}' not found"
        )
    
    logger.info(f"[API] Deleted provider {provider_id} for user {user_id}")
    
    return {"message": f"Provider '{provider_id}' configuration deleted successfully"}


@router.post("/validate", response_model=ValidateProviderResponse)
async def validate_provider_configuration(
    request: ValidateProviderRequest,
    current_user: Any = Depends(get_current_user),
) -> ValidateProviderResponse:
    """
    Validate a provider configuration by making a test API call.
    """
    
    try:
        from ...ai.llm_router import LLMRouter
        
        router = LLMRouter()
        
        # Make a simple test call
        import time
        start_time = time.time()
        
        response = await router.run(
            prompt="Hello, world!",
            model=request.test_model or "gpt-3.5-turbo",
            provider=request.provider_id,
            api_key=request.api_key.get_secret_value(),
            org_id=request.org_id,
            max_tokens=10,
        )
        
        latency = (time.time() - start_time) * 1000
        
        return ValidateProviderResponse(
            provider_id=request.provider_id,
            valid=True,
            test_response=response.text[:100] + ("..." if len(response.text) > 100 else ""),
            latency_ms=latency,
        )
        
    except Exception as e:
        logger.warning(f"[API] Provider validation failed for {request.provider_id}: {e}")
        
        return ValidateProviderResponse(
            provider_id=request.provider_id,
            valid=False,
            error=str(e),
            test_response=None,
        )


@router.get("/models")
async def list_models_for_configured_providers(
    current_user: Any = Depends(get_current_user),
) -> Dict[str, List[str]]:
    """
    List available models for all configured providers.
    
    This helps populate model selection dropdowns in the UI.
    """
    
    user_id = current_user["user_id"]
    user_providers = _get_user_providers(user_id)
    
    try:
        from ...ai.llm_model_registry import list_models, get_provider
        
        provider_models = {}
        
        for provider_id, config in user_providers.items():
            if not config.get("enabled", True):
                continue
                
            provider_info = get_provider(provider_id)
            if provider_info:
                models = list_models(provider_id)
                provider_models[provider_id] = [
                    model.model_id for model in models
                ]
        
        return provider_models
        
    except ImportError:
        logger.warning("Model registry not available")
        return {}


# ---------------------------------------------------------------------------
# Background Tasks
# ---------------------------------------------------------------------------

async def _validate_provider_background(
    user_id: str,
    provider_id: str, 
    api_key: str,
    org_id: Optional[str],
    base_url: Optional[str],
) -> None:
    """
    Background task to validate a provider configuration.
    """
    
    try:
        from ...ai.llm_router import LLMRouter
        
        router = LLMRouter()
        
        # Simple validation call
        await router.run(
            prompt="Test",
            model="gpt-3.5-turbo" if provider_id == "openai" else None,
            provider=provider_id,
            api_key=api_key,
            org_id=org_id,
            max_tokens=5,
        )
        
        # Update validation status
        config = _get_user_providers(user_id).get(provider_id)
        if config:
            import datetime
            config["validation_status"] = "valid"
            config["last_validated"] = datetime.datetime.utcnow().isoformat() + "Z"
            _save_user_provider(user_id, provider_id, config)
        
        logger.info(f"[Background] Provider {provider_id} validated successfully for user {user_id}")
        
    except Exception as e:
        # Update validation status as invalid
        config = _get_user_providers(user_id).get(provider_id)
        if config:
            import datetime
            config["validation_status"] = "invalid"
            config["last_validated"] = datetime.datetime.utcnow().isoformat() + "Z"
            config["validation_error"] = str(e)
            _save_user_provider(user_id, provider_id, config)
        
        logger.warning(f"[Background] Provider {provider_id} validation failed for user {user_id}: {e}")