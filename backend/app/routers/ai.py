from fastapi import APIRouter, HTTPException
from ..schemas import IdeaOptimizeRequest, IdeaOptimizeResponse, KeywordOptimizeRequest, KeywordOptimizeResponse
from ..services.ai import AiServiceError, optimize_idea, optimize_visual_keyword

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/optimize-idea", response_model=IdeaOptimizeResponse)
def api_optimize_idea(payload: IdeaOptimizeRequest) -> IdeaOptimizeResponse:
    try:
        optimized = optimize_idea(payload.idea)
        return IdeaOptimizeResponse(optimized_idea=optimized)
    except AiServiceError as exc:
        raise HTTPException(status_code=502, detail=f"AI optimization failed: {exc}") from exc

@router.post("/optimize-keyword", response_model=KeywordOptimizeResponse)
def api_optimize_keyword(payload: KeywordOptimizeRequest) -> KeywordOptimizeResponse:
    try:
        optimized = optimize_visual_keyword(payload.description, payload.keyword)
        return KeywordOptimizeResponse(optimized_keyword=optimized)
    except AiServiceError as exc:
        raise HTTPException(status_code=502, detail=f"AI optimization failed: {exc}") from exc
