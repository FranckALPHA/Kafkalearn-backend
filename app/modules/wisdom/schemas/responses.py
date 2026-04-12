from pydantic import BaseModel, Field
from typing import Optional

class DailyWisdomResponse(BaseModel):
    tip: dict
    is_new: bool
    date: str
    language: str
    is_fallback: bool = False

class ShareResponse(BaseModel):
    message: str
    texte_partage: str
