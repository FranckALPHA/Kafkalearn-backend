from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class SectionListResponse(BaseModel):
    document_id: int
    document_titre: str
    nb_sections: int
    progression_globale: float
    sections: List[Dict[str, Any]]

class SectionItemsResponse(BaseModel):
    section_id: int
    section_title: str
    nb_items: int
    langue: str
    current_index: int
    items: List[Dict[str, Any]]

class ReviewTodayResponse(BaseModel):
    nb_sections_a_revoir: int
    temps_estime_minutes: int
    sections: List[Dict[str, Any]]

class MemoryStatsResponse(BaseModel):
    total_sections: int
    completed_sections: int
    avg_score: float
    total_reviews: int
    accuracy: float
    streak: int
    next_reviews_due: int
    top_weak_subjects: List[str]
