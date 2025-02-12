from pydantic import BaseModel


class PhoneOut(BaseModel):
    id: int
    phone_number: str


class BuldingOut(BaseModel):
    id: int
    address: str


class ActivityOut(BaseModel):
    id: int
    activity_name: str


class OrganizationOut(BaseModel):
    id: int
    company_name: str
    phones: list[PhoneOut]
    building: BuldingOut
    activities: list[ActivityOut] | None

    class Config:
        from_attributes = True
