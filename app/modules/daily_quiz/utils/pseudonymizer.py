class Pseudonymizer:
    @staticmethod
    def mask_name(name: str, visible_chars: int = 3) -> str:
        if not name:
            return "Anonyme"
        name = name.strip()
        if len(name) <= visible_chars:
            return name + "***"
        return name[:visible_chars] + "***"
