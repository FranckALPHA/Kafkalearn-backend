from pydantic import BaseModel, Field


class CheckReferralCodeRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)
