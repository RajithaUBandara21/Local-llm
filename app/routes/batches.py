from fastapi import APIRouter, BackgroundTasks, Depends, Response, status

from app.dependencies import get_batch_service
from app.schemas import BatchRequest, BatchStatus, ReviewableEmail, ReviewAction, ReviewActionRequest
from app.services.batch import BatchService

router = APIRouter()


@router.post("/api/batches", response_model=BatchStatus)
def create_batch_endpoint(
    request: BatchRequest,
    background_tasks: BackgroundTasks,
    service: BatchService = Depends(get_batch_service)
):
    # start() claims the worker slot, so a second request is refused before this task runs.
    batch = service.start(request.file)
    background_tasks.add_task(service.run, batch.id)
    return batch


@router.get("/api/batches", response_model=list[BatchStatus])
def list_batches_endpoint(service: BatchService = Depends(get_batch_service)):
    return service.list_batches()


@router.get("/api/batches/{batch_id}", response_model=BatchStatus)
def get_batch_endpoint(batch_id: int, service: BatchService = Depends(get_batch_service)):
    return service.get(batch_id)


@router.post("/api/batches/{batch_id}/resume", response_model=BatchStatus)
def resume_batch_endpoint(
    batch_id: int,
    background_tasks: BackgroundTasks,
    service: BatchService = Depends(get_batch_service)
):
    batch = service.resume(batch_id)
    background_tasks.add_task(service.run, batch.id)
    return batch


@router.post("/api/bulk-insert", response_model=BatchStatus)
def bulk_insert_endpoint(
    background_tasks: BackgroundTasks,
    service: BatchService = Depends(get_batch_service)
):
    batch = service.bulk_insert()
    background_tasks.add_task(service.run, batch.id)
    return batch


@router.delete("/api/batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_batch_endpoint(batch_id: int, service: BatchService = Depends(get_batch_service)):
    service.delete(batch_id)


@router.get("/api/emails", response_model=list[ReviewableEmail])
def list_emails_endpoint(batch_id: int | None = None, service: BatchService = Depends(get_batch_service)):
    return service.emails(batch_id)


@router.post("/api/emails/{email_id}/review", response_model=ReviewAction)
def review_email_endpoint(
    email_id: int, request: ReviewActionRequest, service: BatchService = Depends(get_batch_service)
):
    return service.review(email_id, request.action, request.edited_reply)
