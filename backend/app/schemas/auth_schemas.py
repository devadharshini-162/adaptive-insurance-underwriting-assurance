from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "customer"
    phone: Optional[str] = None
    organization: Optional[str] = None
    job_title: Optional[str] = None

class UserCreateInternal(UserCreate):
    role: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: str
    phone: Optional[str] = None
    organization: Optional[str] = None
    job_title: Optional[str] = None

    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    organization: Optional[str] = None
    job_title: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None
