"""
jobs/tasks.py
=============
Tâches Celery asynchrones pour le module users.
"""
import logging
from datetime import datetime, timedelta

from app.modules.users.jobs.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import DATABASE_URL

logger = logging.getLogger(__name__)


def _get_db():
    """Crée une session DB dédiée pour les tâches Celery."""
    engine_session = SessionLocal
    return engine_session()


# ─── Tâches légères ───────────────────────────────────────────────

@celery_app.task(name="users.tasks.update_streak", queue="default", bind=True, max_retries=3)
def update_streak_task(self, user_id: str):
    """Met à jour le streak de connexion."""
    db = _get_db()
    try:
        from app.modules.users.services.streak_service import StreakService
        StreakService(db).calculer_streak(user_id)
        db.commit()
    except Exception as e:
        logger.error(f"Erreur update_streak user {user_id}: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(name="users.tasks.recalc_score", queue="default", bind=True, max_retries=3)
def recalc_score_task(self, user_id: str):
    """Recalcule le score global."""
    db = _get_db()
    try:
        from app.modules.users.services.score_global_service import ScoreGlobalService
        ScoreGlobalService(db).recalculer(user_id)
        db.commit()
    except Exception as e:
        logger.error(f"Erreur recalc_score user {user_id}: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=120)
    finally:
        db.close()


# ─── Tâches lourdes (I/O, LLM, PDF) ─────────────────────────────

@celery_app.task(name="users.tasks.send_otp_email", queue="emails", bind=True, max_retries=2)
def send_otp_email_task(self, user_id: str, email: str, prenom: str, otp_code: str, type: str):
    """Envoi d'email OTP via Brevo/SMTP."""
    try:
        from app.modules.users.services.mail_service import MailService
        MailService().envoyer_otp(email, prenom, otp_code, type)
    except Exception as e:
        logger.error(f"Échec envoi OTP user {user_id}: {e}")
        raise self.retry(exc=e, countdown=30)


@celery_app.task(name="users.tasks.generate_pdf_report", queue="heavy", bind=True, max_retries=2)
def generate_pdf_report_task(self, user_id: str, report_id: int, declencheur: str):
    """
    Génération complète d'un rapport cognitif PDF.
    1. Appel LLM pour le résumé narratif
    2. Génération PDF via ReportLab
    3. Stockage + notification
    """
    db = _get_db()
    try:
        from app.modules.users.services.profile_report_service import ProfileReportService
        from app.modules.users.models import User, UserLearningProfile
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        from reportlab.lib import colors
        from io import BytesIO
        import json

        report_service = ProfileReportService(db)

        # Récupérer les données utilisateur
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        profile = db.query(UserLearningProfile).filter(
            UserLearningProfile.user_id == user_id
        ).first()

        # Appel LLM pour le résumé
        llm_summary = call_llm_for_summary_task.apply(args=[user_id], queue="llm").get(timeout=120)

        # Génération PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm,
            title=f"Rapport d'apprentissage - {user.prenom or 'Utilisateur'}",
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=HexColor('#4F46E5'),
            spaceAfter=6*mm,
        ))
        styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=HexColor('#1E1B4B'),
            spaceBefore=4*mm,
            spaceAfter=2*mm,
        ))
        styles.add(ParagraphStyle(
            name='BodyText',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            spaceAfter=2*mm,
        ))

        story = []

        # Titre
        story.append(Paragraph("Rapport d'Apprentissage", styles['CustomTitle']))
        story.append(Paragraph(
            f"Élève: <b>{user.prenom or 'Utilisateur'}</b><br/>"
            f"Date: {datetime.utcnow().strftime('%d/%m/%Y')}",
            styles['BodyText']
        ))
        story.append(Spacer(1, 5*mm))

        # Résumé narratif du LLM
        if llm_summary and llm_summary.get("resume_narratif"):
            story.append(Paragraph("Synthèse Intelligence Artificielle", styles['SectionHeader']))
            story.append(Paragraph(llm_summary["resume_narratif"], styles['BodyText']))
            story.append(Spacer(1, 3*mm))

        # Lacunes détectées
        if profile and profile.lacunes:
            story.append(Paragraph("Lacunes Identifiées", styles['SectionHeader']))
            lacunes_data = [(["Matière", "Notions à renforcer"])]
            for matiere, notions in profile.lacunes.items():
                if isinstance(notions, list):
                    lacunes_data.append([matiere, ", ".join(notions)])
                else:
                    lacunes_data.append([matiere, str(notions)])

            lacunes_table = Table(lacunes_data, colWidths=[60*mm, 110*mm])
            lacunes_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#4F46E5')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), HexColor('#F8FAFC')),
                ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CBD5E1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#FFFFFF'), HexColor('#F8FAFC')]),
            ]))
            story.append(lacunes_table)
            story.append(Spacer(1, 3*mm))

        # Forces
        if profile and profile.forces:
            story.append(Paragraph("Forces de l'Élève", styles['SectionHeader']))
            forces_data = [(["Matière", "Niveau"])]
            for matiere, niveau in profile.forces.items():
                forces_data.append([matiere, str(niveau)])

            forces_table = Table(forces_data, colWidths=[60*mm, 110*mm])
            forces_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#059669')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), HexColor('#F0FDF4')),
                ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CBD5E1')),
            ]))
            story.append(forces_table)
            story.append(Spacer(1, 3*mm))

        # Recommandations
        if llm_summary and llm_summary.get("recommandations"):
            story.append(Paragraph("Recommandations", styles['SectionHeader']))
            for i, rec in enumerate(llm_summary["recommandations"], 1):
                story.append(Paragraph(f"<b>{i}.</b> {rec}", styles['BodyText']))

        # Build PDF
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        # Sauvegarder le PDF (optionnel : stockage S3 ou local)
        # Pour l'instant, on stocke juste le statut
        file_url = f"/data/profiles/rapport_{user_id}_{report_id[:8]}.pdf"

        # Mise à jour du statut
        report_service.update_rapport_status(report_id, "completed", {
            "rapport_json": llm_summary,
            "file_url": file_url,
            "completed_at": datetime.utcnow().isoformat(),
        })

        # Notification utilisateur
        try:
            from app.modules.notifications.services.notification_service import NotificationService
            notif_db = SessionLocal()
            NotificationService(notif_db).send_to_user(
                user_id=user_id,
                title="Rapport prêt",
                body=f"Ton rapport d'apprentissage est disponible.",
                type_notif="report_ready",
            )
            notif_db.close()
        except Exception:
            pass

        return {"report_id": report_id, "status": "completed", "file_url": file_url}

    except Exception as e:
        logger.error(f"Échec génération rapport {report_id} user {user_id}: {e}")
        db.rollback()
        try:
            ProfileReportService(db).update_rapport_status(report_id, "failed", {
                "error_message": str(e),
                "failed_at": datetime.utcnow().isoformat(),
            })
        except Exception:
            pass
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@celery_app.task(name="users.tasks.call_llm_for_summary", queue="llm", bind=True, max_retries=3)
def call_llm_for_summary_task(self, user_id: str) -> dict:
    """Appel au LLM pour générer le résumé narratif du profil d'apprentissage."""
    try:
        from app.modules.users.models import User, UserLearningProfile
        from app.modules.core.config import settings
        import google.generativeai as genai

        db = _get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    "resume_narratif": f"Profil de l'utilisateur {user_id} non disponible.",
                    "recommandations": ["Données insuffisantes pour générer des recommandations."],
                }

            profile = db.query(UserLearningProfile).filter(
                UserLearningProfile.user_id == user_id
            ).first()

            # Construire le prompt avec les données du profil
            profile_summary = f"""
Élève: {user.prenom or 'Non renseigné'}
Classe: {user.classe or 'Non renseignée'}
Série: {user.serie or 'Non renseignée'}
"""
            if profile:
                lacunes = json.dumps(profile.lacunes, ensure_ascii=False) if profile.lacunes else "Aucune"
                forces = json.dumps(profile.forces, ensure_ascii=False) if profile.forces else "Aucune"
                skills = json.dumps(profile.skills_utilises, ensure_ascii=False) if profile.skills_utilises else "Aucun"
                scores = json.dumps(profile.score_par_matiere, ensure_ascii=False) if profile.score_par_matiere else "Aucun"

                profile_summary += f"""
Lacunes identifiées: {lacunes}
Forces: {forces}
Skills utilisés: {skills}
Scores par matière: {scores}
"""
            # Configurer Gemini
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)

            prompt = f"""
Tu es un assistant pédagogique expert en analyse de profils d'apprentissage.
Analyse le profil suivant et génère:
1. Un résumé narratif (3-4 phrases) des tendances d'apprentissage
2. Trois recommandations concrètes et actionnables pour améliorer les performances

Profil de l'élève:
{profile_summary}

Réponds au format JSON suivant:
{{
  "resume_narratif": "ton résumé ici",
  "recommandations": ["rec 1", "rec 2", "rec 3"]
}}

Réponds uniquement avec le JSON valide, sans markdown ni texte supplémentaire.
"""
            response = model.generate_content(prompt)
            response_text = response.text.strip()

            # Parser la réponse JSON
            # Retirer le markdown code block s'il existe
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[1]
            if response_text.endswith("```"):
                response_text = response_text.rsplit("\n", 1)[0]
            response_text = response_text.strip()

            result = json.loads(response_text)
            return {
                "resume_narratif": result.get("resume_narratif", "Analyse non disponible"),
                "recommandations": result.get("recommandations", []),
            }

        finally:
            db.close()

    except json.JSONDecodeError as e:
        logger.error(f"Erreur parsing JSON réponse LLM user {user_id}: {e}")
        return {
            "resume_narratif": "L'analyse de ton profil est en cours de finalisation.",
            "recommandations": ["Continue à pratiquer régulièrement pour améliorer tes performances."],
        }
    except Exception as e:
        logger.error(f"Erreur appel LLM user {user_id}: {e}")
        raise self.retry(exc=e, countdown=30)


# ─── Tâches cron (Celery Beat) ──────────────────────────────────

@celery_app.task(name="users.tasks.nightly_score_recalc", queue="cron")
def nightly_score_recalc():
    """Recalcule les scores pour tous les users actifs."""
    db = _get_db()
    try:
        from app.modules.users.models import User
        from app.modules.users.services.score_global_service import ScoreGlobalService

        users = db.query(User).filter(
            User.derniere_activite_at >= datetime.utcnow() - timedelta(days=30),
            User.is_deleted == False,
        ).yield_per(100)

        for user in users:
            try:
                ScoreGlobalService(db).recalculer(str(user.id))
                db.commit()
            except Exception as e:
                logger.error(f"Erreur batch score user {user.id}: {e}")
                db.rollback()
                continue
    finally:
        db.close()


@celery_app.task(name="users.tasks.morning_churn_detection", queue="cron")
def morning_churn_detection():
    """Détection des users à risque de churn."""
    db = _get_db()
    try:
        from app.modules.users.services.churn_detector_service import ChurnDetectorService
        ChurnDetectorService(db).detecter_et_alerter()
        db.commit()
    except Exception as e:
        logger.error(f"Erreur churn detection: {e}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="users.tasks.cleanup_expired_tokens", queue="cron")
def cleanup_expired_tokens():
    """Supprime les refresh tokens expirés."""
    db = _get_db()
    try:
        from app.modules.users.models import RefreshToken
        from sqlalchemy import func

        deleted = db.query(RefreshToken).filter(
            RefreshToken.expires_at < func.now()
        ).delete(synchronize_session=False)
        db.commit()
        logger.info(f"Nettoyage: {deleted} tokens expirés supprimés")
    except Exception as e:
        logger.error(f"Erreur cleanup tokens: {e}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="users.tasks.weekly_auto_reports", queue="cron")
def weekly_auto_reports():
    """Génère les rapports hebdomadaires automatiques."""
    db = _get_db()
    try:
        from app.modules.users.models import User
        from app.modules.users.services.profile_report_service import ProfileReportService

        # Users premium/pro avec activité cette semaine
        users = db.query(User).filter(
            User.plan_effectif.in_(["premium", "pro", "unlimited"]),
            User.derniere_activite_at >= datetime.utcnow() - timedelta(days=7),
            User.is_deleted == False,
        ).all()

        report_service = ProfileReportService(db)
        for user in users:
            try:
                report_service.generer_rapport_async(str(user.id), "weekly_auto")
            except Exception as e:
                logger.error(f"Erreur rapport weekly user {user.id}: {e}")
                continue
        db.commit()
    except Exception as e:
        logger.error(f"Erreur weekly reports: {e}")
        db.rollback()
    finally:
        db.close()
