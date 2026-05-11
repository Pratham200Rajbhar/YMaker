from fastapi import APIRouter

router = APIRouter(prefix="/categories", tags=["categories"])

DEFAULT_CATEGORIES = [
    "General",
    "Educational",
    "Entertainment",
    "News",
    "Marketing",
    "Tutorial",
    "Storytelling",
    "Motivational",
    "Gaming",
    "Health & Fitness",
    "Travel",
    "Food & Cooking",
    "Technology"
]

@router.get("", response_model=list[str])
def list_categories() -> list[str]:
    """
    Returns a list of available project categories.
    """
    return DEFAULT_CATEGORIES
