from fastapi import APIRouter, Depends

from app.dependencies import get_assistant_service
from app.schemas import ActiveModelSettings, AvailableModelsResponse, ChatRequest, ModelChangeRequest, TemperatureRequest
from app.services.assistant import AssistantService

router = APIRouter()


@router.post("/api/chat")
def chat_endpoint(
    request: ChatRequest,
    service: AssistantService = Depends(get_assistant_service)
):
    return service.process_chat(request.prompt)


@router.get("/api/models", response_model=AvailableModelsResponse)
def list_available_models_endpoint(service: AssistantService = Depends(get_assistant_service)):
    return AvailableModelsResponse(models=service.list_available_models())


@router.get("/api/model/active", response_model=ActiveModelSettings)
def get_active_model_settings_endpoint(service: AssistantService = Depends(get_assistant_service)):
    model, temperature = service.active_settings()
    return ActiveModelSettings(active_model=model, active_temperature=temperature)


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
