from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: Optional[int] = None
    exp: Optional[int] = None


class LoginRequest(BaseModel):
    username: str
    password: str
