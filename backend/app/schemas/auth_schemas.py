from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserCreateInternal(UserCreate):
    role: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: str

    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str
