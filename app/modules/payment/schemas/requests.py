from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    plan_id: str = Field(..., min_length=1, max_length=20)
