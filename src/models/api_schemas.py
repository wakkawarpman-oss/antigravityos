from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ShodanBannerSchema(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    port: Optional[int] = None
    product: Optional[str] = None
    vulns: list[str] = Field(default_factory=list)
    shodan_meta: dict[str, Any] = Field(default_factory=dict, alias="_shodan")


class ShodanResponseSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: list[ShodanBannerSchema] = Field(default_factory=list)


class CensysResultSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    hits: list[dict[str, Any]] = Field(default_factory=list)


class CensysSearchResponseSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: CensysResultSchema = Field(default_factory=CensysResultSchema)


class NmapServiceSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    address: str
    port: int
    product: str = ""
    version: str = ""


class OpenDataBotEntitySchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    name: Optional[str] = None
    full_name: Optional[str] = None
    entity_type: str = "company"
    source: str = ""
    address: str = ""
    status: str = ""
    registration_date: str = ""
    primary_activity: str = ""
    phones: list[str] = Field(default_factory=list)


class WebSearchResultSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str
    title: str = ""
    snippet: str = ""


class LeakHit(BaseModel):
    model_config = ConfigDict(extra="allow")

    phone: Optional[str] = Field(default=None, pattern=r"^\+(?:380\d{9}|7\d{10})$")
    email: Optional[str] = Field(default=None, pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    source_file: str
    username: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class GhuntProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    gaia_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    display_name: Optional[str] = None
    profile_photo_url: Optional[str] = None
