# ─────────────────────────────────────────────────────────────────────
# KafkaLearn Backend — Makefile
#
# Usage :
#   make run          # Setup complet + lancement du serveur
#   make setup        # Installation des dépendances uniquement
#   make server       # Lancement du serveur seul
#   make docker       # Démarrage de l'infrastructure Docker
#   make test         # Tests rapides des dépendances
#   make clean        # Nettoyage du cache
# ─────────────────────────────────────────────────────────────────────

.PHONY: run setup server docker test clean install-ocr install-poppler help

# ── Configuration ───────────────────────────────────────────────────
PORT ?= 9880
HOST ?= 0.0.0.0
RELOAD ?= --reload

# ── Couleurs ────────────────────────────────────────────────────────
GREEN  := \033[0;32m
YELLOW := \033[1;33m
RED    := \033[0;31m
NC     := \033[0m

# ── Cible principale ────────────────────────────────────────────────
run: setup server

# ── Setup complet ───────────────────────────────────────────────────
setup: install-uv install-deps install-fastembed install-ocr install-poppler install-magic
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════$(NC)"
	@echo "  KafkaLearn Backend — Dépendances prêtes"
	@echo "$(GREEN)═══════════════════════════════════════════════════$(NC)"

install-uv:
	@if command -v uv > /dev/null 2>&1; then \
		echo "$(GREEN)[✓]$(NC) uv : $$(uv --version)"; \
	else \
		echo "$(YELLOW)[!](NC) uv non trouvé, installation..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
		export PATH="$$HOME/.local/bin:$$PATH"; \
	fi

install-deps:
	@if [ -d ".venv" ] && .venv/bin/python -c "import fastapi" 2>/dev/null; then \
		echo "$(GREEN)[✓]$(NC) Dépendances Python : OK"; \
	else \
		echo "$(YELLOW)[!](NC) Installation des dépendances Python..."; \
		uv sync; \
	fi

install-fastembed:
	@if .venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')" 2>/dev/null; then \
		echo "$(GREEN)[✓]$(NC) FastEmbed + modèle : OK"; \
	else \
		echo "$(YELLOW)[!](NC) Téléchargement du modèle FastEmbed..."; \
		.venv/bin/python -c "from fastembed import TextEmbedding; print('  Téléchargement en cours...'); TextEmbedding(model_name='BAAI/bge-small-en-v1.5'); print('  Modèle prêt.')" 2>&1 | sed 's/^/  /' || echo "$(RED)[✗]$(NC) Échec — sera fait au premier usage du serveur"; \
	fi

install-ocr:
	@if command -v tesseract > /dev/null 2>&1; then \
		echo "$(GREEN)[✓]$(NC) Tesseract OCR : $$(tesseract --version 2>&1 | head -1 | cut -d' ' -f2)"; \
		if tesseract --list-langs 2>/dev/null | grep -q "fra"; then \
			echo "$(GREEN)[✓]$(NC) Données françaises OCR : OK"; \
		else \
			echo "$(YELLOW)[!]$(NC) Installation des données françaises..."; \
			if command -v apt-get > /dev/null 2>&1; then \
				sudo apt-get install -y -qq tesseract-ocr-fra; \
			elif command -v brew > /dev/null 2>&1; then \
				brew install tesseract-lang; \
			fi; \
		fi; \
	else \
		echo "$(YELLOW)[!](NC) Installation de Tesseract OCR..."; \
		if command -v apt-get > /dev/null 2>&1; then \
			sudo apt-get update -qq && sudo apt-get install -y -qq tesseract-ocr tesseract-ocr-fra; \
		elif command -v brew > /dev/null 2>&1; then \
			brew install tesseract tesseract-lang; \
		elif command -v yum > /dev/null 2>&1; then \
			sudo yum install -y tesseract; \
		elif command -v pacman > /dev/null 2>&1; then \
			sudo pacman -S --noconfirm tesseract tesseract-data-fra; \
		else \
			echo "$(RED)[✗]$(NC) Gestionnaire de paquets non reconnu. Installez tesseract-ocr manuellement."; \
		fi; \
	fi

install-poppler:
	@if command -v pdfinfo > /dev/null 2>&1; then \
		echo "$(GREEN)[✓]$(NC) Poppler (pdf2image) : OK"; \
	else \
		echo "$(YELLOW)[!](NC) Installation de Poppler..."; \
		if command -v apt-get > /dev/null 2>&1; then \
			sudo apt-get install -y -qq poppler-utils; \
		elif command -v brew > /dev/null 2>&1; then \
			brew install poppler; \
		elif command -v yum > /dev/null 2>&1; then \
			sudo yum install -y poppler-utils; \
		elif command -v pacman > /dev/null 2>&1; then \
			sudo pacman -S --noconfirm poppler; \
		fi; \
	fi

install-magic:
	@if .venv/bin/python -c "import magic" 2>/dev/null; then \
		echo "$(GREEN)[✓]$(NC) python-magic : OK"; \
	else \
		echo "$(YELLOW)[!]$(NC) Installation de libmagic (optionnel)..."; \
		if command -v apt-get > /dev/null 2>&1; then \
			sudo apt-get install -y -qq libmagic1 2>/dev/null || echo "$(YELLOW)  libmagic requis manuellement$(NC)"; \
		elif command -v brew > /dev/null 2>&1; then \
			brew install libmagic 2>/dev/null || echo "$(YELLOW)  libmagic requis manuellement$(NC)"; \
		fi; \
		uv pip install python-magic 2>/dev/null || echo "$(YELLOW)  python-magic optionnel — la détection MIME utilisera un fallback$(NC)"; \
	fi

# ── Serveur ─────────────────────────────────────────────────────────
server:
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════$(NC)"
	@echo "  KafkaLearn Backend — Serveur"
	@echo "  Port: $(PORT) | Reload: $(RELOAD)"
	@echo "$(GREEN)═══════════════════════════════════════════════════$(NC)"
	@echo ""
	uv run uvicorn app.main:app --host $(HOST) --port $(PORT) $(RELOAD)

# ── Docker ──────────────────────────────────────────────────────────
docker:
	@echo "$(YELLOW)[!](NC) Démarrage de l'infrastructure Docker..."; \
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# ── Tests ───────────────────────────────────────────────────────────
test:
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════$(NC)"
	@echo "  KafkaLearn Backend — Test des dépendances"
	@echo "$(GREEN)═══════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo -n "  uv             : " && (command -v uv > /dev/null 2>&1 && echo "$(GREEN)[✓] $(uv --version)$(NC)" || echo "$(RED)[✗]$(NC)")
	@echo -n "  Python FastAPI : " && (.venv/bin/python -c "import fastapi" 2>/dev/null && echo "$(GREEN)[✓]$(NC)" || echo "$(RED)[✗]$(NC)")
	@echo -n "  FastEmbed      : " && (.venv/bin/python -c "import fastembed" 2>/dev/null && echo "$(GREEN)[✓]$(NC)" || echo "$(RED)[✗]$(NC)")
	@echo -n "  Tesseract OCR  : " && (command -v tesseract > /dev/null 2>&1 && echo "$(GREEN)[✓] $(tesseract --version 2>&1 | head -1 | cut -d' ' -f2)$(NC)" || echo "$(RED)[✗]$(NC)")
	@echo -n "  Poppler        : " && (command -v pdfinfo > /dev/null 2>&1 && echo "$(GREEN)[✓]$(NC)" || echo "$(RED)[✗]$(NC)")
	@echo -n "  python-magic   : " && (.venv/bin/python -c "import magic" 2>/dev/null && echo "$(GREEN)[✓]$(NC)" || echo "$(RED)[✗]$(NC)")
	@echo ""

# ── Nettoyage ───────────────────────────────────────────────────────
clean:
	@echo "$(YELLOW)[!](NC) Nettoyage des caches..."; \
	rm -rf __pycache__ **/__pycache__ .ruff_cache; \
	echo "$(GREEN)[✓]$(NC) Caches Python supprimés"

clean-venv:
	@echo "$(YELLOW)[!](NC) Suppression du venv..."; \
	rm -rf .venv; \
	echo "$(GREEN)[✓]$(NC) Venv supprimé (relancez 'make setup')"

clean-cache:
	@echo "$(YELLOW)[!](NC) Nettoyage du cache FastEmbed..."; \
	rm -rf /tmp/fastembed_cache; \
	echo "$(GREEN)[✓]$(NC) Cache FastEmbed supprimé"

# ── Aide ────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "$(GREEN)KafkaLearn Backend — Makefile$(NC)"
	@echo ""
	@echo "  $(YELLOW)make run$(NC)          Setup complet + lancement du serveur"
	@echo "  $(YELLOW)make setup$(NC)        Installation des dépendances uniquement"
	@echo "  $(YELLOW)make server$(NC)       Lancement du serveur seul"
	@echo "  $(YELLOW)make docker$(NC)       Démarrage de l'infrastructure Docker"
	@echo "  $(YELLOW)make docker-down$(NC)  Arrêt de l'infrastructure Docker"
	@echo "  $(YELLOW)make test$(NC)         Tests rapides des dépendances"
	@echo "  $(YELLOW)make clean$(NC)        Nettoyage des caches"
	@echo "  $(YELLOW)make clean-venv$(NC)   Suppression du venv"
	@echo "  $(YELLOW)make help$(NC)         Affiche cette aide"
	@echo ""
