#!/usr/bin/env python3
"""
Script final pour nettoyer les imports.
"""

import os
import re

def clean_file(filepath):
    """Nettoie les imports dans un fichier."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Pattern pour les imports sqlalchemy multilignes
    # On va réécrire complètement les imports
    lines = content.split('\n')
    new_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Détecter le début d'un import sqlalchemy multiligne
        if line.strip().startswith('from sqlalchemy import (') and i+1 < len(lines):
            # Collecter toutes les lignes jusqu'à la parenthèse fermante
            import_lines = [line]
            j = i + 1
            while j < len(lines) and ')' not in lines[j]:
                import_lines.append(lines[j])
                j += 1
            if j < len(lines):
                import_lines.append(lines[j])
            
            # Reconstruire l'import
            full_import = '\n'.join(import_lines)
            
            # Extraire tous les noms d'import
            match = re.search(r'from sqlalchemy import \((.*?)\)', full_import, re.DOTALL)
            if match:
                imports_text = match.group(1)
                # Nettoyer et séparer
                imports = []
                for part in imports_text.split(','):
                    part = part.strip()
                    if part:
                        # Supprimer les nouvelles lignes
                        part = part.replace('\n', ' ').strip()
                        imports.append(part)
                
                # Supprimer les doublons en gardant l'ordre
                unique_imports = []
                seen = set()
                for imp in imports:
                    if imp not in seen:
                        seen.add(imp)
                        unique_imports.append(imp)
                
                # Vérifier si TIMESTAMP et func sont présents
                has_timestamp = 'TIMESTAMP' in unique_imports
                has_func = 'func' in unique_imports
                
                # Ajouter TIMESTAMP et func s'ils manquent (mais normalement ils devraient être là)
                if not has_timestamp:
                    unique_imports.append('TIMESTAMP')
                if not has_func:
                    unique_imports.append('func')
                
                # Reconstruire l'import sur une seule ligne si possible
                if len(unique_imports) <= 8:  # Limite arbitraire pour une ligne
                    new_import = f'from sqlalchemy import ({", ".join(unique_imports)})'
                    new_lines.append(new_import)
                else:
                    # Format multiligne
                    new_import = 'from sqlalchemy import (\n    ' + ',\n    '.join(unique_imports) + '\n)'
                    new_lines.append(new_import)
                
                i = j  # Avancer à la ligne après la parenthèse fermante
            else:
                # Garder les lignes originales si le pattern ne match pas
                new_lines.extend(import_lines)
                i = j
        else:
            new_lines.append(line)
            i += 1
    
    content = '\n'.join(new_lines)
    
    # Corriger les cas spécifiques
    content = content.replace('from sqlalchemy import (TIMESTAMP\n    Column,', 'from sqlalchemy import (\n    Column,')
    content = content.replace('TIMESTAMP,\n    TIMESTAMP,', 'TIMESTAMP,')
    content = re.sub(r'TIMESTAMP,\s+TIMESTAMP', 'TIMESTAMP', content)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return False

def main():
    # Tous les fichiers modifiés
    files = [
        'app/modules/users/models/user.py',
        'app/modules/calendar/models/calendar_session.py',
        'app/modules/daily_quiz/models/daily_quiz_attempt.py',
        # Ajouter d'autres fichiers problématiques si nécessaire
    ]
    
    # D'abord, vérifier tous les fichiers pour trouver ceux avec des problèmes
    all_files = []
    for root, dirs, files_in_dir in os.walk('app'):
        for file in files_in_dir:
            if file.endswith('.py'):
                all_files.append(os.path.join(root, file))
    
    problematic = []
    
    for filepath in all_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Vérifier les problèmes courants
            if ('from sqlalchemy import (' in content and 
                ('(, TIMESTAMP' in content or 
                 'TIMESTAMP,\n    TIMESTAMP' in content or
                 'from sqlalchemy import (TIMESTAMP\n    Column' in content)):
                problematic.append(filepath)
        except:
            pass
    
    print(f"Fichiers problématiques trouvés: {len(problematic)}")
    
    fixed = []
    for filepath in problematic:
        try:
            if clean_file(filepath):
                fixed.append(filepath)
                print(f"✓ {filepath}")
        except Exception as e:
            print(f"✗ Erreur avec {filepath}: {e}")
    
    print(f"\nTotal nettoyés: {len(fixed)} fichiers")

if __name__ == '__main__':
    main()
