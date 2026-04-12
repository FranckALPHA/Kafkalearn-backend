ALLOWED_EXTENSIONS = {".pdf", ".docx"}
BLACKLISTED_DIRS = ["/etc", "/var", "/root", "/boot", "/dev", "/proc", "/sys", "/tmp", "/usr"]
MAX_FILE_SIZE_MB = 50
MIME_TYPE_MAP = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "docx",
}
