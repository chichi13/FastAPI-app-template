from datetime import datetime

from pydantic import BaseModel, EmailStr, constr


class UserProfileBase(BaseModel):
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    province: str | None = None
    postcode: str | None = None


class UserProfile(UserProfileBase):
    id: int

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    username: constr(to_lower=True, min_length=4, max_length=30, strip_whitespace=True)
    email: EmailStr


class UserCreate(UserBase):
    password: constr(min_length=8, max_length=255)
    email: EmailStr


class UserInDBBase(UserBase):
    id: int
    created_at: datetime = None
    updated_at: datetime = None

    class Config:
        from_attributes = True


class UserInDBProfile(UserInDBBase):
    profile: UserProfile | None = None


class UserUpdate(UserInDBBase):
    username: (
        constr(to_lower=True, min_length=4, max_length=30, strip_whitespace=True) | None
    ) = None
    email: EmailStr | None = None
    password: constr(min_length=8, max_length=60) | None = None
    is_active: bool | None = None


class UserSchema(UserInDBBase):
    pass


class UserSchemaProfile(UserInDBProfile):
    pass


class UserInDB(UserInDBBase):
    password: constr(min_length=8)
