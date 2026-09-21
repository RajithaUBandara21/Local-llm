from fastapi import APIRouter, Depends

from app.dependencies import get_assistant_service
from app.schemas import ChatRequest, ModelChangeRequest, TemperatureRequest
from app.services.assistant import AssistantService

router = APIRouter()


@router.post("/api/chat")
def chat_endpoint(
    request: ChatRequest,
    service: AssistantService = Depends(get_assistant_service)
):
    return service.process_chat(request.prompt)


@router.post("/api/model/change")
def change_model_endpoint(
    request: ModelChangeRequest,
    service: AssistantService = Depends(get_assistant_service)
):
    new_model = service.switch_active_model(request.model_name)
    return {"status": "success", "message": f"Switched active model to {new_model}"}


@router.post("/api/settings/temperature")
def set_temperature_endpoint(
    request: TemperatureRequest,
    service: AssistantService = Depends(get_assistant_service)
):
    new_temp = service.update_temperature(request.temperature)
    return {"status": "success", "active_temperature": new_temp}
