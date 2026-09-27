from typing import Literal

from pydantic import BaseModel, Field


class SystemOverview(BaseModel):
    orchestrators: int
    appliances: int
    selected_appliances: int
    compatibility_profiles: int
    services: dict[str, str]


class AppearanceSettings(BaseModel):
    primary: str = Field(default="#2FBF9B", pattern=r"^#[0-9a-fA-F]{6}$")
    secondary: str = Field(default="#E6B655", pattern=r"^#[0-9a-fA-F]{6}$")
    header: str = Field(default="#0C0F11", pattern=r"^#[0-9a-fA-F]{6}$")
    background: str = Field(default="#0F1214", pattern=r"^#[0-9a-fA-F]{6}$")
    surface: str = Field(default="#171B1E", pattern=r"^#[0-9a-fA-F]{6}$")
    text: str = Field(default="#F3F5F4", pattern=r"^#[0-9a-fA-F]{6}$")
    icon: Literal["network", "activity", "gauge", "workflow"] = "network"
    font: Literal["inter", "system", "humanist", "technical", "mono"] = "inter"
    panel_name: str = Field(default="DashboardAPI", min_length=3, max_length=80)
    welcome_message: str = Field(
        default="Inventario y capacidades obtenidas desde las APIs de EdgeConnect",
        max_length=240,
    )


class UpdateRequest(BaseModel):
    version: str = Field(
        pattern=r"^v\d+\.\d+\.\d+-stable$"
    )
    confirmation: str = Field(min_length=8, max_length=160)
