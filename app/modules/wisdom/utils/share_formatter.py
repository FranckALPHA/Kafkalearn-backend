class ShareFormatter:
    @staticmethod
    def format_for_whatsapp(
        text: str, author: str, app_name: str = "Kafkalearn"
    ) -> str:
        return f'"{text}" — {author}\n\n📚 Révise avec moi sur {app_name} !'
