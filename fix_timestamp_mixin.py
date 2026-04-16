#!/usr/bin/env python3
"""
Script simplifié pour remplacer TimestampMixin.
"""

import os
import re
import sys

def add_imports(content):
    """Ajoute TIMESTAMP et func aux imports sqlalchemy si nécessaire."""
    lines = content.split('\n')
    new_lines = []
    
    has_timestamp = False
    has_func = False
    
    # Vérifier si TIMESTAMP et func sont déjà importés
    for line in lines:
        if 'from sqlalchemy import' in line:
            if 'TIMESTAMP' in line:
                has_timestamp = True
            if 'func' in line:
                has_func = True
        if 'from sqlalchemy.sql import func' in line:
            has_func = True
    
    # Parcourir les lignes pour ajouter les imports manquants
    for i, line in enumerate(lines):
        if 'from sqlalchemy import' in line and not has_timestamp:
            # Ajouter TIMESTAMP
            if ')' in line:
                # Format sur une ligne avec parenthèses
                line = line.replace(')', ', TIMESTAMP)')
            else:
                # Format sur une ligne sans parenthèses
                if line.strip().endswith(','):
                    line += ' TIMESTAMP'
                else:
                    line += ', TIMESTAMP'
            has_timestamp = True
        
        if 'from sqlalchemy import' in line and not has_func:
            # Ajouter func
            if ')' in line:
                line = line.replace(')', ', func)')
            else:
                if line.strip().endswith(','):
                    line += ' func'
                else:
                    line += ', func'
            has_func = True
        
        new_lines.append(line)
    
    # Si func n'a pas été ajouté mais qu'il y a un import séparé, on le laisse
    return '\n'.join(new_lines)

def process_model_file(filepath):
    """Traite un fichier de modèle."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Étape 1: Ajouter les imports nécessaires
    content = add_imports(content)
    
    # Étape 2: Supprimer l'import de TimestampMixin
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        if 'from app.modules.users.models.mixins import TimestampMixin' in line:
            if ', SoftDeleteMixin' in line:
                # Garder seulement SoftDeleteMixin
                new_line = line.replace('TimestampMixin, ', '').replace(', TimestampMixin', '')
                new_lines.append(new_line)
            else:
                # Supprimer complètement la ligne
                continue
        elif 'from .mixins import TimestampMixin' in line:
            if ', SoftDeleteMixin' in line:
                # Garder seulement SoftDeleteMixin
                new_line = line.replace('TimestampMixin, ', '').replace(', TimestampMixin', '')
                new_lines.append(new_line)
            else:
                # Supprimer complètement la ligne
                continue
        else:
            new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    # Étape 3: Retirer TimestampMixin de l'héritage de classe
    # Chercher toutes les classes avec TimestampMixin
    class_pattern = r'class\s+(\w+)\s*\(([^)]*TimestampMixin[^)]*)\)'
    
    def replace_class_match(match):
        class_name = match.group(1)
        bases = match.group(2)
        
        # Retirer TimestampMixin
        new_bases = bases.replace('TimestampMixin, ', '').replace(', TimestampMixin', '')
        
        return f'class {class_name}({new_bases})'
    
    content = re.sub(class_pattern, replace_class_match, content, flags=re.MULTILINE)
    
    # Étape 4: Ajouter les colonnes created_at et updated_at
    # Chercher la classe modifiée
    class_def_pattern = r'class\s+(\w+)\s*\([^)]*\):'
    class_match = re.search(class_def_pattern, content, re.MULTILINE)
    
    if class_match:
        class_start = class_match.start()
        # Trouver le bloc de la classe
        class_content = content[class_start:]
        
        # Trouver __tablename__
        tablename_pattern = r'__tablename__\s*=\s*"[^"]+"'
        tablename_match = re.search(tablename_pattern, class_content, re.MULTILINE)
        
        if tablename_match:
            tablename_end = tablename_match.end()
            # Trouver où insérer après __tablename__
            insert_pos = class_start + tablename_end
            
            # Vérifier si les colonnes existent déjà
            if 'created_at = Column(TIMESTAMP' not in content:
                # Préparer l'insertion
                columns = '\n    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)\n    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)'
                
                # Insérer après __tablename__
                before = content[:insert_pos]
                after = content[insert_pos:]
                
                # S'assurer qu'on insère après la ligne __tablename__
                if not before.endswith('\n'):
                    before += '\n'
                
                content = before + columns + after
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return False

def process_init_file(filepath):
    """Traite un fichier __init__.py."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        if 'from .mixins import TimestampMixin, SoftDeleteMixin' in line:
            new_lines.append('from .mixins import SoftDeleteMixin')
        elif 'from .mixins import TimestampMixin' in line:
            # Supprimer la ligne
            continue
        elif 'from app.modules.users.models.mixins import TimestampMixin, SoftDeleteMixin' in line:
            new_lines.append('from app.modules.users.models.mixins import SoftDeleteMixin')
        elif 'from app.modules.users.models.mixins import TimestampMixin' in line:
            # Supprimer la ligne
            continue
        else:
            new_lines.append(line)
    
    new_content = '\n'.join(new_lines)
    
    if new_content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    
    return False

def main():
    # Liste des fichiers à traiter (obtenue précédemment)
    files_to_process = [
        'app/modules/calendar/models/calendar_personal_study.py',
        'app/modules/calendar/models/calendar_session.py',
        'app/modules/calendar/models/calendar_timetable.py',
        'app/modules/calendar/models/daily_suggestions_cache.py',
        'app/modules/calendar/models/session_ping_log.py',
        'app/modules/daily_quiz/models/daily_quiz.py',
        'app/modules/daily_quiz/models/daily_quiz_attempt.py',
        'app/modules/daily_quiz/models/monthly_leaderboard.py',
        'app/modules/doc_analysis/models/analysis_feedback.py',
        'app/modules/doc_analysis/models/document_analysis.py',
        'app/modules/epreuves/models/document.py',
        'app/modules/epreuves/models/document_chunk.py',
        'app/modules/epreuves/models/document_view.py',
        'app/modules/epreuves/models/playlist.py',
        'app/modules/ingest/models/ingest_job.py',
        'app/modules/ingest/models/metadata_queue.py',
        'app/modules/ingest/models/worker_job.py',
        'app/modules/library/models/asset_copy.py',
        'app/modules/library/models/asset_rating.py',
        'app/modules/library/models/pedagogical_asset.py',
        'app/modules/memory/models/concept_graph.py',
        'app/modules/memory/models/memory_item.py',
        'app/modules/memory/models/memory_item_attempt.py',
        'app/modules/memory/models/memory_section.py',
        'app/modules/memory/models/user_section_progress.py',
        'app/modules/notifications/models/device.py',
        'app/modules/notifications/models/notification_log.py',
        'app/modules/notifications/models/notification_preference.py',
        'app/modules/payment/models/plan_price.py',
        'app/modules/payment/models/transaction.py',
        'app/modules/referral/models/referral_activity.py',
        'app/modules/referral/models/referral_reward.py',
        'app/modules/school/models/school.py',
        'app/modules/school/models/school_invitation_csv.py',
        'app/modules/school/models/school_member.py',
        'app/modules/search/models/search_chunk_returned.py',
        'app/modules/search/models/search_log.py',
        'app/modules/skills/models/chat_message.py',
        'app/modules/skills/models/chat_session.py',
        'app/modules/skills/models/mixins.py',
        'app/modules/skills/models/quiz_session.py',
        'app/modules/skills/models/skill_usage_log.py',
        'app/modules/user_documents/models/user_document.py',
        'app/modules/user_documents/models/user_document_chunk.py',
        'app/modules/users/models/__init__.py',
        'app/modules/users/models/user.py',
        'app/modules/users/models/user_activity.py',
        'app/modules/users/models/user_feedback.py',
        'app/modules/users/models/user_learning_profile.py',
        'app/modules/users/models/user_learning_signals.py',
        'app/modules/wisdom/models/wisdom_tip.py',
        'app/modules/wisdom/models/wisdom_user_interaction.py',
    ]
    
    modified = []
    
    for filepath in files_to_process:
        if not os.path.exists(filepath):
            print(f"Fichier non trouvé: {filepath}")
            continue
        
        try:
            if filepath.endswith('__init__.py'):
                if process_init_file(filepath):
                    modified.append(filepath)
                    print(f"✓ {filepath}")
                else:
                    print(f"  {filepath} (pas de modifications nécessaires)")
            elif filepath.endswith('mixins.py'):
                # Ne pas modifier le fichier source de TimestampMixin
                print(f"  {filepath} (fichier source, ignoré)")
            else:
                if process_model_file(filepath):
                    modified.append(filepath)
                    print(f"✓ {filepath}")
                else:
                    print(f"  {filepath} (pas de modifications nécessaires)")
        except Exception as e:
            print(f"✗ Erreur avec {filepath}: {e}")
    
    print(f"\nTotal modifié: {len(modified)} fichiers")

if __name__ == '__main__':
    main()
