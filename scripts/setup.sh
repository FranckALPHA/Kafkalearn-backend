#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# scripts/setup.sh — KafkaLearn Backend Setup & Dependency Check
#
# Usage :
#   bash scripts/setup.sh          # Installation complète
#   bash scripts/setup.sh --skip-uv # Skip uv sync (pour Docker)
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ─────────────────────────────────────────────────────────────────────
# 1. Vérifier / installer uv
# ─────────────────────────────────────────────────────────────────────
check_uv() {
    if command -v uv &> /dev/null; then
        log_info "uv déjà installé : $(uv --version)"
    else
        log_warn "uv non trouvé, installation..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
        if ! command -v uv &> /dev/null; then
            log_error "Échec de l'installation de uv. Assurez-vous que curl est installé."
            exit 1
        fi
        log_info "uv installé : $(uv --version)"
    fi
}

# ─────────────────────────────────────────────────────────────────────
# 2. Vérifier / installer Python dependencies (uv sync)
# ─────────────────────────────────────────────────────────────────────
check_python_deps() {
    SKIP_UV="${SKIP_UV:-false}"
    if [ "$SKIP_UV" = "true" ]; then
        log_info "Skip uv sync (--skip-uv activé)"
        return
    fi

    # Vérifier si le venv existe déjà
    if [ -d ".venv" ] && [ -f ".venv/bin/python" ]; then
        # Vérifier si les dépendances clés sont installées
        if .venv/bin/python -c "import fastapi" 2>/dev/null; then
            log_info "Environnement Python OK — skipping uv sync (forcez avec --force-sync)"
            return
        fi
    fi

    log_info "Installation des dépendances Python via uv sync..."
    uv sync
    log_info "Dépendances Python installées"
}

# ─────────────────────────────────────────────────────────────────────
# 3. Vérifier / installer FastEmbed model
# ─────────────────────────────────────────────────────────────────────
check_fastembed_model() {
    log_info "Vérification du modèle FastEmbed..."

    # Le modèle est téléchargé au premier import de fastembed
    # On vérifie simplement que le package est installé
    UV_PYTHON=".venv/bin/python"
    if [ ! -f "$UV_PYTHON" ]; then
        UV_PYTHON="python3"
    fi

    if $UV_PYTHON -c "import fastembed; print('  fastembed:', fastembed.__version__)" 2>/dev/null; then
        # Vérifier si le modèle est déjà en cache
        CACHE_DIR="${HOME}/.cache/fastembed"
        if [ -d "$CACHE_DIR" ] && [ "$(ls -A $CACHE_DIR 2>/dev/null)" ]; then
            log_info "  Modèle FastEmbed déjà en cache : $CACHE_DIR"
        else
            log_warn "  Modèle FastEmbed non en cache — il sera téléchargé au premier usage"
            # Pré-téléchargement optionnel
            log_info "  Pré-téléchargement du modèle BAAI/bge-small-en-v1.5..."
            $UV_PYTHON -c "
from fastembed import TextEmbedding
print('  Téléchargement en cours...')
model = TextEmbedding(model_name='BAAI/bge-small-en-v1.5')
print('  Modèle prêt.')
" 2>&1 | sed 's/^/    /' || log_warn "  Échec du pré-téléchargement (sera fait au premier usage)"
        fi
    else
        log_error "  fastembed non installé — lancez 'uv sync' d'abord"
        return 1
    fi
}

# ─────────────────────────────────────────────────────────────────────
# 4. Vérifier / installer Tesseract OCR
# ─────────────────────────────────────────────────────────────────────
check_tesseract() {
    log_info "Vérification de Tesseract OCR..."

    if command -v tesseract &> /dev/null; then
        TESS_VERSION=$(tesseract --version 2>&1 | head -1)
        log_info "  Tesseract OK : $TESS_VERSION"
    else
        log_warn "  Tesseract non trouvé, tentative d'installation..."

        # Détecter le gestionnaire de paquets
        if command -v apt-get &> /dev/null; then
            sudo apt-get update -qq
            sudo apt-get install -y -qq tesseract-ocr tesseract-ocr-fra
        elif command -v brew &> /dev/null; then
            brew install tesseract tesseract-lang
        elif command -v yum &> /dev/null; then
            sudo yum install -y tesseract
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm tesseract tesseract-data-fra
        else
            log_error "  Gestionnaire de paquets non reconnu. Installez tesseract-ocr manuellement."
            return 1
        fi

        if command -v tesseract &> /dev/null; then
            log_info "  Tesseract installé : $(tesseract --version 2>&1 | head -1)"
        else
            log_error "  Échec de l'installation de Tesseract"
            return 1
        fi
    fi

    # Vérifier les data françaises
    if tesseract --list-langs 2>/dev/null | grep -q "fra"; then
        log_info "  Données françaises OCR : OK"
    else
        log_warn "  Données françaises manquantes, installation..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y -qq tesseract-ocr-fra
        elif command -v brew &> /dev/null; then
            brew install tesseract-lang
        fi
        log_info "  Données françaises installées"
    fi
}

# ─────────────────────────────────────────────────────────────────────
# 5. Vérifier / installer Poppler (pdf2image)
# ─────────────────────────────────────────────────────────────────────
check_poppler() {
    log_info "Vérification de Poppler (pdf2image)..."

    if command -v pdfinfo &> /dev/null; then
        log_info "  Poppler OK : $(pdfinfo -v 2>&1 | head -1)"
    else
        log_warn "  Poppler non trouvé, tentative d'installation..."

        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y -qq poppler-utils
        elif command -v brew &> /dev/null; then
            brew install poppler
        elif command -v yum &> /dev/null; then
            sudo yum install -y poppler-utils
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm poppler
        else
            log_error "  Gestionnaire de paquets non reconnu. Installez poppler-utils manuellement."
            return 1
        fi

        if command -v pdfinfo &> /dev/null; then
            log_info "  Poppler installé"
        else
            log_error "  Échec de l'installation de Poppler"
            return 1
        fi
    fi
}

# ─────────────────────────────────────────────────────────────────────
# 6. Vérifier les dépendances système optionnelles
# ─────────────────────────────────────────────────────────────────────
check_optional_deps() {
    log_info "Vérification des dépendances optionnelles..."

    # python-magic (détection MIME)
    UV_PYTHON=".venv/bin/python"
    if [ ! -f "$UV_PYTHON" ]; then
        UV_PYTHON="python3"
    fi

    if ! $UV_PYTHON -c "import magic" 2>/dev/null; then
        log_warn "  python-magic non installé, installation..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y -qq libmagic1
        elif command -v brew &> /dev/null; then
            brew install libmagic
        fi
        uv pip install python-magic 2>/dev/null || log_warn "  Échec installation python-magic"
    else
        log_info "  python-magic : OK"
    fi
}

# ─────────────────────────────────────────────────────────────────────
# 7. Résumé
# ─────────────────────────────────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "  KafkaLearn Backend — Setup Complet"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""

    # uv
    if command -v uv &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} uv : $(uv --version)"
    else
        echo -e "  ${RED}✗${NC} uv : NON INSTALLÉ"
    fi

    # Python deps
    UV_PYTHON=".venv/bin/python"
    if [ -f "$UV_PYTHON" ] && $UV_PYTHON -c "import fastapi" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Dépendances Python : OK"
    else
        echo -e "  ${RED}✗${NC} Dépendances Python : MANQUANTES (lancez 'uv sync')"
    fi

    # FastEmbed
    if [ -f "$UV_PYTHON" ] && $UV_PYTHON -c "import fastembed" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} FastEmbed : OK"
    else
        echo -e "  ${RED}✗${NC} FastEmbed : MANQUANT"
    fi

    # Tesseract
    if command -v tesseract &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} Tesseract OCR : $(tesseract --version 2>&1 | head -1 | cut -d' ' -f2)"
    else
        echo -e "  ${RED}✗${NC} Tesseract OCR : NON INSTALLÉ"
    fi

    # Poppler
    if command -v pdfinfo &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} Poppler (pdf2image) : OK"
    else
        echo -e "  ${RED}✗${NC} Poppler : NON INSTALLÉ"
    fi

    echo ""
    echo -e "  ${YELLOW}Pour démarrer le serveur :${NC}"
    echo -e "    uv run uvicorn app.main:app --port 9880 --reload"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   KafkaLearn Backend — Setup & Dependency Check          ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Parse arguments
    for arg in "$@"; do
        case $arg in
            --skip-uv)
                export SKIP_UV=true
                ;;
            --force-sync)
                rm -rf .venv
                ;;
        esac
    done

    check_uv
    check_python_deps
    check_fastembed_model
    check_tesseract
    check_poppler
    check_optional_deps
    print_summary
}

main "$@"
