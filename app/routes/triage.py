from fastapi import APIRouter, Depends

from app.dependencies import get_triage_service
from app.schemas import TriageRequest, TriageResponse
from app.services.triage import TriageService

router = APIRouter()


@router.post("/api/triage", response_model=TriageResponse)
def triage_endpoint(
    request: TriageRequest,
    service: TriageService = Depends(get_triage_service)
):
    return service.triage(request)
