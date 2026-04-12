ASSET_TYPES = ["FICHE", "QUIZ", "CORRIGE", "EPREUVE", "SOLVER", "MEMORY_PACK", "VISUALISATION"]
PLAN_HIERARCHY = ["freemium", "access", "premium", "pro", "unlimited", "school"]
PLAN_REQUIREMENTS = {
    "FICHE": "access",
    "QUIZ": "access",
    "CORRIGE": "access",
    "EPREUVE": "pro",
    "SOLVER": "access",
    "MEMORY_PACK": "access",
    "VISUALISATION": "pro",
}
SHARE_CODE_PREFIX = "AST"
SHARE_CODE_LENGTH = 6
MAX_FILE_SIZE_MB = 20
ALLOWED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg"]
