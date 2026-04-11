"""
models/chat_message.py
======================
Table chat_messages — Messages individuels dans une session.
"""
class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"
    
    # ─── Identifiants ────────────────────────────────────────────
    id = Column(Integer, primary_key=True)  # BIGINTEGER via sequence
    session_id = Column(UUID(as_uuid=True), ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # ─── Contenu message ─────────────────────────────────────────
    role = Column(String(10), CheckConstraint("role IN ('user','assistant','system')"), nullable=False)
    content = Column(Text, nullable=False)  # texte brut
    
    # ─── Métadonnées génération (assistant uniquement) ───────────
    skill_utilise = Column(String(20), nullable=True)  # skill qui a généré
    output_type = Column(String(10), CheckConstraint("output_type IN ('text','pdf','json','png')"), nullable=True)
    file_url = Column(String(500), nullable=True)  # URL fichier généré
    json_data = Column(JSONB, nullable=True)  # données structurées (quiz, solver)
    
    # ─── Contexte pédagogique ────────────────────────────────────
    matiere = Column(String(100), nullable=True, index=True)
    niveau = Column(String(50), nullable=True)
    
    # ─── Métriques performance ───────────────────────────────────
    latence_ms = Column(Integer, nullable=True)
    tokens_utilises = Column(Integer, nullable=True)
    llm_provider = Column(String(20), nullable=True)  # gemini, mistral...
    
    # ─── Feedback utilisateur ────────────────────────────────────
    feedback = Column(SMALLINT, CheckConstraint("feedback IN (-1, 1)"), nullable=True)  # -1 ou 1
    feedback_at = Column(TIMESTAMP, nullable=True)
    
    # ─── Gestion erreurs ─────────────────────────────────────────
    erreur_code = Column(String(50), nullable=True)  # code erreur si échec
    
    # ─── Idempotency ─────────────────────────────────────────────
    idempotency_key = Column(String(100), unique=True, nullable=True, index=True)
    
    # ─── Relations ───────────────────────────────────────────────
    session = relationship("ChatSession", back_populates="messages")
    
    # ─── Index composites ────────────────────────────────────────
    __table_args__ = (
        Index('idx_session_created', 'session_id', 'created_at'),  # historique trié
        Index('idx_feedback_skill', 'skill_utilise', 'feedback'),  # analytics qualité
    )
    
    # ─── Méthodes utilitaires ────────────────────────────────────
    def is_assistant_message(self) -> bool:
        return self.role == 'assistant'
    
    def has_generated_content(self) -> bool:
        return self.is_assistant_message() and (self.file_url or self.json_data or self.content)
    
    def serialize_for_chat(self) -> dict:
        """Sérialisation pour affichage dans le chat."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "skill_utilise": self.skill_utilise,
            "output_type": self.output_type,
            "file_url": self.file_url,
            "json_data": self.json_data if self.output_type == 'json' else None,
            "feedback": self.feedback,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }