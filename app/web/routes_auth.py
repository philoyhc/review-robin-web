from fastapi import APIRouter, Depends

from app.auth.identity import AuthenticatedUser, get_current_user

router = APIRouter()


@router.get("/me")
def me(user: AuthenticatedUser = Depends(get_current_user)) -> dict[str, object]:
    return {
        "principal_id": user.principal_id,
        "email": user.email,
        "name": user.name,
        "provider": user.provider,
        "is_fake": user.is_fake,
    }
