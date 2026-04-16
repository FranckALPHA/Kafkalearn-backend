#!/usr/bin/env python3
"""
Script pour remplacer TimestampMixin dans tous les fichiers de l'application.
"""

import os
import re
import sys
from pathlib import Path

def process_file(filepath):
    """Traite un fichier pour remplacer TimestampMixin."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Vérifier si le fichier importe TimestampMixin
    if 'TimestampMixin' not in content:
        return False
    
    # Vérifier si c'est le fichier mixins.py lui-même
    if filepath.endswith('app/modules/users/models/mixins.py'):
        # On ne modifie pas le fichier source de TimestampMixin
        return False
    
    # Vérifier si c'est un fichier __init__.py
    if filepath.endswith('__init__.py'):
        # Pour les fichiers __init__.py, on supprime seulement l'import de TimestampMixin
        # mais on garde SoftDeleteMixin si présent
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            if 'from .mixins import TimestampMixin, SoftDeleteMixin' in line:
                # Remplacer par seulement SoftDeleteMixin
                new_lines.append('from .mixins import SoftDeleteMixin')
            elif 'from .mixins import TimestampMixin' in line:
                # Supprimer complètement la ligne
                continue
            elif 'from app.modules.users.models.mixins import TimestampMixin, SoftDeleteMixin' in line:
                # Remplacer par seulement SoftDeleteMixin
                new_lines.append('from app.modules.users.models.mixins import SoftDeleteMixin')
            elif 'from app.modules.users.models.mixins import TimestampMixin' in line:
                # Supprimer complètement la ligne
                continue
            else:
                new_lines.append(line)
        
        new_content = '\n'.join(new_lines)
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        return False
    
    # Pour les fichiers de modèles, on doit faire plusieurs modifications
    # 1. Ajouter les imports nécessaires (TIMESTAMP, func) s'ils ne sont pas déjà présents
    # 2. Supprimer l'import de TimestampMixin
    # 3. Ajouter les colonnes created_at et updated_at dans la classe
    # 4. Retirer TimestampMixin de l'héritage de la classe
    
    # Vérifier si le fichier a déjà TIMESTAMP importé
    has_timestamp_import = 'TIMESTAMP' in content and ('from sqlalchemy import' in content or 'from sqlalchemy import ' in content)
    has_func_import = 'func' in content and ('from sqlalchemy import' in content or 'from sqlalchemy.sql import func' in content)
    
    # Extraire les lignes pour les modifier
    lines = content.split('\n')
    new_lines = []
    
    # Étape 1: Traiter les imports
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Gérer l'import de TimestampMixin
        if 'from app.modules.users.models.mixins import TimestampMixin' in line:
            # Cas 1: Import seul de TimestampMixin
            if ', SoftDeleteMixin' not in line:
                # Supprimer la ligne complètement
                i += 1
                continue
            # Cas 2: Import avec SoftDeleteMixin
            else:
                # Remplacer par seulement SoftDeleteMixin
                new_lines.append(line.replace('TimestampMixin, ', '').replace(', TimestampMixin', ''))
                i += 1
                continue
        elif 'from .mixins import TimestampMixin' in line:
            # Cas similaire pour les imports relatifs
            if ', SoftDeleteMixin' not in line:
                # Supprimer la ligne complètement
                i += 1
                continue
            else:
                # Remplacer par seulement SoftDeleteMixin
                new_lines.append(line.replace('TimestampMixin, ', '').replace(', TimestampMixin', ''))
                i += 1
                continue
        
        # Ajouter TIMESTAMP et func aux imports sqlalchemy si nécessaire
        if 'from sqlalchemy import' in line and not has_timestamp_import:
            # Vérifier si TIMESTAMP n'est pas déjà dans l'import
            if 'TIMESTAMP' not in line:
                # Ajouter TIMESTAMP à la fin de la liste d'imports
                if line.endswith(')'):
                    # Format multiligne
                    # On va gérer ce cas plus tard
                    pass
                else:
                    # Format sur une ligne
                    if line.strip().endswith(')'):
                        line = line.replace(')', ', TIMESTAMP)')
                    else:
                        line = line.rstrip()
                        if line.endswith(','):
                            line += ' TIMESTAMP'
                        else:
                            line += ', TIMESTAMP'
                has_timestamp_import = True
        
        if 'from sqlalchemy import' in line and not has_func_import:
            # Vérifier si func n'est pas déjà dans l'import
            if 'func' not in line:
                # Ajouter func à la fin de la liste d'imports
                if line.endswith(')'):
                    # Format multiligne
                    pass
                else:
                    # Format sur une ligne
                    if line.strip().endswith(')'):
                        line = line.replace(')', ', func)')
                    else:
                        line = line.rstrip()
                        if line.endswith(','):
                            line += ' func'
                        else:
                            line += ', func'
                has_func_import = True
        
        new_lines.append(line)
        i += 1
    
    # Reconstruire le contenu
    content = '\n'.join(new_lines)
    
    # Étape 2: Trouver la définition de la classe et modifier l'héritage
    # Rechercher la classe qui hérite de TimestampMixin
    class_pattern = r'class\s+(\w+)\s*\(\s*[^)]*TimestampMixin[^)]*\)'
    match = re.search(class_pattern, content, re.MULTILINE)
    
    if not match:
        # Aucune classe avec TimestampMixin trouvée
        return False
    
    class_def = match.group(0)
    class_name = match.group(1)
    
    # Retirer TimestampMixin de la liste d'héritage
    new_class_def = class_def.replace('TimestampMixin, ', '').replace(', TimestampMixin', '')
    
    # Remplacer l'ancienne définition par la nouvelle
    content = content.replace(class_def, new_class_def)
    
    # Étape 3: Ajouter les colonnes created_at et updated_at dans la classe
    # Trouver la position après __tablename__
    tablename_pattern = r'__tablename__\s*=\s*"[^"]+"'
    tablename_match = re.search(tablename_pattern, content, re.MULTILINE)
    
    if tablename_match:
        tablename_pos = tablename_match.end()
        # Trouver la prochaine ligne qui n'est pas vide ou un commentaire
        lines_after = content[tablename_pos:].split('\n')
        
        # Chercher où insérer les colonnes (après __tablename__ et avant la première colonne ou méthode)
        insert_pos = tablename_pos
        for j, line in enumerate(lines_after):
            if line.strip() and not line.strip().startswith('#'):
                # C'est le début du contenu de la classe
                break
            insert_pos += len(line) + 1
        
        # Préparer les colonnes à ajouter
        columns_to_add = '\n    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)\n    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)'
        
        # Insérer les colonnes
        content = content[:insert_pos] + columns_to_add + content[insert_pos:]
    
    # Écrire le fichier modifié
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return False

def main():
    # Trouver tous les fichiers Python dans app/
    python_files = []
    for root, dirs, files in os.walk('app'):
        # Exclure .venv et autres répertoires cachés
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    # Traiter chaque fichier
    modified_files = []
    for filepath in python_files:
        try:
            if process_file(filepath):
                modified_files.append(filepath)
                print(f"✓ Modifié: {filepath}")
        except Exception as e:
            print(f"✗ Erreur avec {filepath}: {e}")
    
    print(f"\nTotal de fichiers modifiés: {len(modified_files)}")
    
    # Afficher la liste des fichiers modifiés
    if modified_files:
        print("\nFichiers modifiés:")
        for f in modified_files:
            print(f"  - {f}")

if __name__ == '__main__':
    main()
