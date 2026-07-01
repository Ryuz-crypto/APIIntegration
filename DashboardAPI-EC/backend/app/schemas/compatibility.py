from pydantic import BaseModel


class OperationResolveRequest(BaseModel):
    version: str
    operation_id: str
    path_params: dict[str, str] = {}


class OperationResolveResponse(BaseModel):
    version: str
    operation_id: str
    method: str
    path: str
    polling_hint_seconds: int | None = None
    notes: list[str] = []


class CompatibilityProfileRead(BaseModel):
    version: str
    status: str
    source: str
    operations: list[str]


class SwaggerLoadResult(BaseModel):
    version: str
    status: str
    operation_count: int
    message: str
