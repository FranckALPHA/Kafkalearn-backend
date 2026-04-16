#!/usr/bin/env python3
"""
Script pour corriger les fichiers spécifiques avec des problèmes d'import.
"""

import re

def fix_user_py():
    """Corrige app/modules/users/models/user.py"""
    with open('app/modules/users/models/user.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remplacer la section d'import problématique
    # Trouver la section from sqlalchemy import
    lines = content.split('\n')
    new_lines = []
    
    i = 0
    while i < len(lines):
        if lines[i].strip() == 'from sqlalchemy import (':
            # Reconstruire proprement l'import
            new_lines.append('from sqlalchemy import (')
            new_lines.append('    Column,')
            new_lines.append('    String,')
            new_lines.append('    Boolean,')
            new_lines.append('    Float,')
            new_lines.append('    Integer,')
            new_lines.append('    TIMESTAMP,')
            new_lines.append('    CheckConstraint,')
            new_lines.append('    Index,')
            new_lines.append('    ForeignKey,')
            new_lines.append('    func,')
            new_lines.append(')')
            # Sauter les anciennes lignes jusqu'à la parenthèse fermante
            i += 1
            while i < len(lines) and ')' not in lines[i]:
                i += 1
            i += 1  # Sauter la ligne avec ')'
            # Sauter la ligne 19 qui a un ')' supplémentaire
            if i < len(lines) and lines[i].strip() == ')':
                i += 1
        else:
            new_lines.append(lines[i])
            i += 1
    
    content = '\n'.join(new_lines)
    
    with open('app/modules/users/models/user.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ app/modules/users/models/user.py corrigé")

def fix_notification_log_py():
    """Corrige app/modules/notifications/models/notification_log.py"""
    with open('app/modules/notifications/models/notification_log.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remplacer la section problématique
    content = content.replace('    TIMESTAMP     Column,', '    TIMESTAMP,')
    content = content.replace('    TIMESTAMP,\n    TIMESTAMP,', '    TIMESTAMP,')
    
    # Supprimer les doublons
    lines = content.split('\n')
    new_lines = []
    
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith('from sqlalchemy import'):
            # Collecter tout l'import
            import_start = i
            while i < len(lines) and ')' not in lines[i]:
                i += 1
            if i < len(lines):
                i += 1  # Inclure la ligne avec ')'
            
            # Extraire et nettoyer les imports
            import_block = lines[import_start:i]
            import_text = '\n'.join(import_block)
            
            # Extraire les noms
            match = re.search(r'from sqlalchemy import \((.*?)\)', import_text, re.DOTALL)
            if match:
                imports_text = match.group(1)
                imports = []
                for part in imports_text.split(','):
                    part = part.strip()
                    if part:
                        imports.append(part)
                
                # Supprimer les doublons
                unique_imports = []
                seen = set()
                for imp in imports:
                    if imp not in seen:
                        seen.add(imp)
                        unique_imports.append(imp)
                
                # Reconstruire
                new_import = 'from sqlalchemy import (\n    ' + ',\n    '.join(unique_imports) + '\n)'
                new_lines.append(new_import)
            else:
                new_lines.extend(import_block)
        else:
            new_lines.append(lines[i])
            i += 1
    
    content = '\n'.join(new_lines)
    
    with open('app/modules/notifications/models/notification_log.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ app/modules/notifications/models/notification_log.py corrigé")

if __name__ == '__main__':
    fix_user_py()
    fix_notification_log_py()
