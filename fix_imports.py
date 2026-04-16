#!/usr/bin/env python3
"""
Script pour corriger les imports cassés par le script précédent.
"""

import os
import re

def fix_file(filepath):
    """Corrige les imports dans un fichier."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Corriger le pattern "from sqlalchemy import (, TIMESTAMP"
    content = re.sub(r'from sqlalchemy import \(\s*, TIMESTAMP', 'from sqlalchemy import (TIMESTAMP', content)
    
    # Corriger le pattern "from sqlalchemy import (, TIMESTAMP, func"
    content = re.sub(r'from sqlalchemy import \(\s*, TIMESTAMP,\s*func', 'from sqlalchemy import (TIMESTAMP, func', content)
    
    # Corriger le pattern "from sqlalchemy import (, func"
    content = re.sub(r'from sqlalchemy import \(\s*, func', 'from sqlalchemy import (func', content)
    
    # Supprimer les doublons dans la liste d'imports
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        # Vérifier les lignes d'import sqlalchemy
        if 'from sqlalchemy import' in line and '(' in line:
            # Extraire le contenu entre parenthèses
            match = re.search(r'from sqlalchemy import \((.*)\)', line)
            if match:
                imports = match.group(1)
                # Nettoyer les espaces et séparer
                imports_list = [imp.strip() for imp in imports.split(',') if imp.strip()]
                # Supprimer les doublons
                unique_imports = []
                seen = set()
                for imp in imports_list:
                    if imp not in seen:
                        seen.add(imp)
                        unique_imports.append(imp)
                # Reconstruire la ligne
                if unique_imports:
                    new_line = f'from sqlalchemy import ({", ".join(unique_imports)})'
                    new_lines.append(new_line)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return False

def main():
    # Liste des fichiers modifiés
    files = [
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
        'app/modules/skills/models/quiz_session.py',
        'app/modules/skills/models/skill_usage_log.py',
        'app/modules/user_documents/models/user_document.py',
        'app/modules/user_documents/models/user_document_chunk.py',
        'app/modules/users/models/user.py',
        'app/modules/users/models/user_activity.py',
        'app/modules/users/models/user_feedback.py',
        'app/modules/users/models/user_learning_profile.py',
        'app/modules/users/models/user_learning_signals.py',
        'app/modules/wisdom/models/wisdom_tip.py',
        'app/modules/wisdom/models/wisdom_user_interaction.py',
    ]
    
    fixed = []
    
    for filepath in files:
        if not os.path.exists(filepath):
            print(f"Fichier non trouvé: {filepath}")
            continue
        
        try:
            if fix_file(filepath):
                fixed.append(filepath)
                print(f"✓ {filepath}")
            else:
                print(f"  {filepath} (pas de corrections nécessaires)")
        except Exception as e:
            print(f"✗ Erreur avec {filepath}: {e}")
    
    print(f"\nTotal corrigé: {len(fixed)} fichiers")

if __name__ == '__main__':
    main()
