"""
utils/csv_parser.py
===================
Parsing sécurisé de fichiers CSV pour l'import d'élèves.
"""
import csv
import io
import re
from typing import List, Dict, Tuple
from fastapi import HTTPException


class CSVParseError(Exception):
    pass


class CSVParser:
    MAX_FILE_SIZE_MB = 2
    MAX_LINES = 500
    REQUIRED_COLUMNS = ["email", "prenom"]
    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    @classmethod
    def validate_file(cls, file_content: bytes, filename: str) -> bool:
        if len(file_content) > cls.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(413, f"FILE_TOO_LARGE: max {cls.MAX_FILE_SIZE_MB}MB")
        if not filename.lower().endswith(".csv"):
            raise HTTPException(400, "INVALID_EXTENSION: fichier CSV requis")
        return True

    @classmethod
    def parse(cls, file_content: bytes) -> Tuple[List[Dict], List[Dict]]:
        try:
            content = file_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = file_content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(content))

        if not reader.fieldnames:
            raise CSVParseError("CSV vide ou format invalide")

        missing_cols = set(cls.REQUIRED_COLUMNS) - set(reader.fieldnames)
        if missing_cols:
            raise CSVParseError(f"Colonnes manquantes: {missing_cols}")

        valid_rows = []
        errors = []

        for line_num, row in enumerate(reader, start=2):
            if line_num > cls.MAX_LINES + 1:
                errors.append({"ligne": line_num, "email": row.get("email", ""), "raison": f"Limite de {cls.MAX_LINES} lignes dépassée"})
                break

            email = row.get("email", "").strip().lower()
            prenom = row.get("prenom", "").strip()
            nom = row.get("nom", "").strip()

            if not email:
                errors.append({"ligne": line_num, "email": "", "raison": "Email requis"})
                continue

            if not cls.EMAIL_REGEX.match(email):
                errors.append({"ligne": line_num, "email": email, "raison": "Format email invalide"})
                continue

            if len(email) > 255:
                errors.append({"ligne": line_num, "email": email, "raison": "Email trop long"})
                continue

            valid_rows.append({"email": email, "prenom": prenom or "Élève", "nom": nom, "ligne": line_num})

        return valid_rows, errors
