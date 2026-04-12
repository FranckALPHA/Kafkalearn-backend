# Contrats d'intégration — Module School

## → Appel vers `users`
```python
user.plan_effectif = "school"  # ou "freemium"
user.school_id = school_id  # ou None
db.commit()
```

## → Appel vers `payment`
```python
checkout = await PaymentService(db).initier_paiement_ecole(
    school_id=school.id, nb_sieges=new_seat_count, callback_url=...
)
# Après webhook → SchoolExpirationService.reactiver_ecole(school_id, nouvelle_expiration)
```

## → Appel vers `notifications`
```python
await NotificationService(db).send_to_user(user_id=admin_id, title=f"Expiration: {jours_restants} jours", ...)
await NotificationService(db).send_email(to_email=student_email, subject="Bienvenue", template="school_invitation", ...)
```

## ← Appel depuis `core/quota`
```python
if user.plan_effectif == "school":
    quota_ok = await SchoolQuotaService(db, redis).verifier_et_consommer_quota(school_id=user.school_id, nb_eleves_max=school.nb_eleves_max)
    if not quota_ok:
        raise HTTPException(402, "QUOTA_SCHOOL_DEPASSE")
```

## 📡 Endpoints

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| POST | `/api/v1/school/creer` | ✅ Email vérifié | Créer école (trial 30j) |
| POST | `/api/v1/school/rejoindre` | ✅ | Rejoindre via code |
| GET | `/api/v1/school/dashboard` | ✅ Membre | Dashboard école |
| GET | `/api/v1/school/tarifs` | Public | Grille tarifaire |
| DELETE | `/api/v1/school/supprimer` | ✅ Admin | Supprimer école |
| GET/POST/DELETE | `/api/v1/school/members/*` | ✅ Admin | Gestion membres + CSV |
| GET/POST | `/api/v1/school/billing/*` | ✅ Admin | Facturation |
| GET/POST | `/api/v1/admin/school/*` | ✅ SuperAdmin | Admin global |
