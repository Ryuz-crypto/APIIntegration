from pydantic import BaseModel


class SystemOverview(BaseModel):
    orchestrators: int
    appliances: int
    selected_appliances: int
    compatibility_profiles: int
    services: dict[str, str]
