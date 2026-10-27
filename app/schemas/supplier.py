from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

CountryCode = Annotated[
    str,
    Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$", examples=["UA"]),
    AfterValidator(str.upper),
]


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, examples=["Zaporizhzhia Alu Recycling"])
    country: CountryCode
    contact_email: EmailStr


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    country: CountryCode | None = None
    contact_email: EmailStr | None = None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str
    contact_email: str
