class Pseudonymizer:
    @staticmethod
    def mask_name(name: str, visible_chars: int = 3) -> str:
        if not name:
            return "Anonyme"
        name = name.strip()
        if len(name) <= visible_chars:
            return name + "***"
        return name[:visible_chars] + "***"

    @staticmethod
    def mask_email(email: str) -> str:
        if not email or "@" not in email:
            return "***@***"
        local, domain = email.rsplit("@", 1)
        if len(local) <= 3:
            return "***@" + domain
        return local[:3] + "***@" + domain
