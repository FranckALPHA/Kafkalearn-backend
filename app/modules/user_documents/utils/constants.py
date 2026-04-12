ALLOWED_MIME_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
]
MAX_FILE_SIZE_MB = 20
PLAN_QUOTAS = {
    "freemium": (5, 10 * 1024 * 1024),
    "access": (20, 50 * 1024 * 1024),
    "premium": (50, 100 * 1024 * 1024),
    "pro": (200, 500 * 1024 * 1024),
    "unlimited": (500, 2 * 1024 * 1024 * 1024),
    "school": (200, 500 * 1024 * 1024),
}
