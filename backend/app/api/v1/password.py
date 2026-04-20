from fastapi import APIRouter

from app.schemas.password import GenerateRequest, GenerateResponse, ValidateRequest, ValidateResponse
from app.services.password_generator import generate_password, generate_batch
from app.services.password_validator import validate_password

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate(body: GenerateRequest):
    passwords = generate_batch(
        count=body.count,
        length=body.length,
        include_uppercase=body.include_uppercase,
        include_digits=body.include_digits,
        include_special=body.include_special,
        exclude_similar=body.exclude_similar,
        exclude_ambiguous=body.exclude_ambiguous,
    )
    return GenerateResponse(passwords=passwords)


@router.post("/validate", response_model=ValidateResponse)
async def validate(body: ValidateRequest):
    result = validate_password(body.password)
    return ValidateResponse(**result)
