from fastapi import APIRouter

router = APIRouter()


# Prefixed: inside a mount `url_for` resolves through the host's router,
# where an unprefixed name finds the first mount that has it.
@router.get("/health", name="utilities_health")
def health() -> dict[str, str]:
    return {"status": "ok"}
