from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal


class SearchRequest(BaseModel):
    """Requête de recherche hybride."""
    texte: str = Field(..., min_length=3, max_length=500, description="Texte de la requête")
    avec_ia: bool = Field(False, description="Générer une réponse IA")
    mode_ia: Optional[Literal["reponse", "resume", "exercices_similaires"]] = Field(None)
    top_k: int = Field(10, ge=1, le=50, description="Nombre de résultats")
    poids_semantique: float = Field(0.7, ge=0.0, le=1.0, description="Poids ANN vs BM25")
    enrichir_contexte: bool = Field(False, description="Enrichir les chunks avec contexte voisin")

    # Filtres
    matiere: Optional[str] = Field(None, max_length=100)
    niveau: Optional[str] = Field(None, max_length=50)
    serie: Optional[str] = Field(None, max_length=20)
    annee: Optional[int] = Field(None, ge=2000, le=2030)
    type_doc: Optional[str] = Field(None, max_length=20)

    session_id: Optional[str] = Field(None, max_length=36)

    def to_filters_dict(self) -> dict:
        """Convertit les filtres en dict pour Vespa."""
        return {
            "matiere": self.matiere,
            "niveau": self.niveau,
            "serie": self.serie,
            "annee": self.annee,
            "type_doc": self.type_doc,
        }

    @field_validator("texte")
    @classmethod
    def texte_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le texte ne peut pas être vide")
        return v.strip()


class FeedbackRequest(BaseModel):
    """Feedback utilisateur sur une recherche."""
    rating: int = Field(..., ge=1, le=5, description="Note de 1 à 5")
    commentaire: Optional[str] = Field(None, max_length=500)


class LiteSearchRequest(BaseModel):
    """Recherche textuelle simple (Meilisearch)."""
    q: str = Field(..., min_length=2, max_length=200)
    matiere: Optional[str] = None
    niveau: Optional[str] = None
    limit: int = Field(10, ge=1, le=30)
