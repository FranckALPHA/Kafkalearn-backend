class QuestionValidator:
    @staticmethod
    def validate_qcm(question: dict) -> bool:
        required = ["enonce", "options", "bonne_reponse", "explication"]
        if not all(k in question for k in required):
            return False
        if not isinstance(question["options"], list) or len(question["options"]) < 2:
            return False
        if question["bonne_reponse"] not in question["options"]:
            return False
        return True

    @staticmethod
    def validate_true_false(question: dict) -> bool:
        required = ["enonce", "bonne_reponse", "explication"]
        if not all(k in question for k in required):
            return False
        if not isinstance(question["bonne_reponse"], bool):
            return False
        return True

    @classmethod
    def validate(cls, question: dict, quiz_type: str = "qcm") -> bool:
        if quiz_type == "qcm":
            return cls.validate_qcm(question)
        elif quiz_type == "true_false":
            return cls.validate_true_false(question)
        return True  # Default pass for other types
