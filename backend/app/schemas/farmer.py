import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.db.models.enums import PreferredLanguage

# Generic international format: optional leading +, 8-15 digits total, no
# leading zero after the optional +. Not Uzbekistan-specific on purpose —
# farmers/agronomists may register with any country code.
PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{7,14}$")


class FarmerCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200, examples=["Aliyev Vali"])
    phone: str = Field(..., examples=["+998901234567"])
    email: EmailStr | None = Field(default=None, examples=["farmer@example.com"])
    region: str = Field(..., min_length=2, max_length=100, examples=["Toshkent viloyati"])
    district: str = Field(..., min_length=2, max_length=100, examples=["Zangiota tumani"])
    preferred_language: PreferredLanguage = PreferredLanguage.UZ

    @field_validator("full_name", "region", "district")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, value: str) -> str:
        value = value.strip()
        if not PHONE_PATTERN.match(value):
            raise ValueError("phone must be a valid international number, e.g. +998901234567")
        return value


class FarmerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    phone: str
    email: str | None
    region: str
    district: str
    preferred_language: PreferredLanguage
    created_at: datetime
    updated_at: datetime
