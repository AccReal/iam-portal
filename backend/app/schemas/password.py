from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    length: int = Field(default=16, ge=4, le=128)
    include_uppercase: bool = True
    include_digits: bool = True
    include_special: bool = True
    exclude_similar: bool = False
    exclude_ambiguous: bool = False
    count: int = Field(default=1, ge=1, le=50)


class GenerateResponse(BaseModel):
    passwords: list[str]


class ValidateRequest(BaseModel):
    password: str


class ValidateResponse(BaseModel):
    score: int
    strength: str
    strength_level: int  # 0-4
    feedback: list[str]
    crack_time: str
    length: int
    has_uppercase: bool
    has_lowercase: bool
    has_digits: bool
    has_special: bool
