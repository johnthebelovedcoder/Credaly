"""
API Key Management Router — /v1/api-keys
Per PRD FR-032: API key authentication and management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.schemas import (
    ApiKeyInfo,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    ErrorResponse,
    RotateApiKeyResponse,
)
from src.services.api_key.service import ApiKeyService

router = APIRouter(prefix="/api-keys", tags=["API Key Management"])


@router.get(
    "",
    response_model=list[ApiKeyInfo],
    responses={401: {"model": ErrorResponse}},
    summary="List all API keys",
    description="Retrieve all API keys.",
)
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
):
    """GET /v1/api-keys — List all API keys."""
    service = ApiKeyService(db)
    return await service.get_api_keys()


@router.post(
    "",
    response_model=CreateApiKeyResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Create a new API key",
    description="Generate a new API key. The raw key is shown only once.",
)
async def create_api_key(
    request: CreateApiKeyRequest,
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/api-keys — Create API key."""
    service = ApiKeyService(db)
    
    try:
        api_key_info, raw_key = await service.create_api_key(
            name=request.name,
            environment=request.environment,
        )
        
        return CreateApiKeyResponse(
            key=api_key_info,
            rawApiKey=raw_key,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                code="API_KEY_CREATION_FAILED",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )


@router.post(
    "/{key_id}/rotate",
    response_model=RotateApiKeyResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Rotate an API key",
    description="Deactivate the old key and create a new one.",
)
async def rotate_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
):
    """POST /v1/api-keys/:id/rotate — Rotate API key."""
    service = ApiKeyService(db)
    
    try:
        api_key_info, raw_key = await service.rotate_api_key(key_id)
        
        return RotateApiKeyResponse(
            key=api_key_info,
            rawApiKey=raw_key,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code="API_KEY_NOT_FOUND",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                code="API_KEY_ROTATION_FAILED",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )


@router.delete(
    "/{key_id}",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Revoke an API key",
    description="Deactivate an API key. This action cannot be undone.",
)
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
):
    """DELETE /v1/api-keys/:id — Revoke API key."""
    service = ApiKeyService(db)
    
    try:
        await service.revoke_api_key(key_id)
        
        return {
            "success": True,
            "message": f"API key '{key_id}' has been revoked",
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code="API_KEY_NOT_FOUND",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                code="API_KEY_REVOCATION_FAILED",
                message=str(e),
                trace_id="unknown",
            ).model_dump(),
        )
