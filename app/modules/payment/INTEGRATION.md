# Payment Module — Integration Guide

## Overview

The `payment` module handles payment initialization via NotchPay (XAF/Cameroon mobile money),
webhook processing with HMAC validation, subscription management, transaction history,
and admin analytics (MRR, conversion rates, pending transactions).

---

## Endpoints

### User endpoints (`/payment`)

| Method | Path                     | Description                                  | Auth             |
|--------|--------------------------|----------------------------------------------|------------------|
| GET    | `/payment/plans`         | Liste des plans avec `is_current`            | Optional (auth)  |
| POST   | `/payment/checkout/{plan_id}` | Initie paiement NotchPay               | Required + email verified |
| GET    | `/payment/callback`      | Callback après paiement → redirect frontend  | None (query: `reference`) |
| GET    | `/payment/history`       | Historique des transactions (paginé)         | Required         |
| GET    | `/payment/status`        | Statut abonnement + quota IA + jours restants| Required         |

### Webhook endpoint (`/payment/webhook`)

| Method | Path                    | Description                          | Auth          |
|--------|-------------------------|--------------------------------------|---------------|
| POST   | `/payment/webhook/`     | Reçoit webhooks NotchPay (HMAC only) | HMAC signature only |

### Admin endpoints (`/admin/payment`)

| Method | Path                        | Description                          | Auth        |
|--------|-----------------------------|--------------------------------------|-------------|
| GET    | `/admin/payment/analytics`  | MRR, conversion rate, pending count  | Admin only  |
| GET    | `/admin/payment/pending`    | Transactions bloquées en attente     | Admin only  |
| POST   | `/admin/payment/retry/{reference}` | Relance manuelle d'une transaction | Admin only  |

---

## Integration Contracts

### Users module (`app.modules.users`)

**After payment completion** — the `validate_subscription_task` updates the user's plan:

```python
from app.modules.payment.jobs import validate_subscription_task

# Called by WebhookService after payment.complete event
validate_subscription_task.delay(transaction_id)
```

Fields updated on `User`:
- `plan_effectif` → set to `transaction.plan_id`
- `plan_expiration_at` → `now + 30 days`

**After school payment** — the `_reactiver_membres_ecole` method reactivates all school members:

```python
# In PaymentService
payment_service._reactiver_membres_ecole(school_id)
# Sets plan_effectif="school" and plan_expiration_at=+30d for all users with that school_id
```

### Notifications module (`app.modules.notifications`)

**Payment confirmation** — sent after successful payment:

```python
from app.modules.payment.jobs import notify_payment_complete_task

notify_payment_complete_task.delay(user_id, plan_id)
# Internally calls NotificationService.envoyer_template with template_type="payment_confirm"
```

**Churn relance** — weekly task sends notifications to users who didn't renew:

```python
from app.modules.payment.jobs import detect_churn_task
# Runs weekly (Sunday 7h), calls NotificationService with template_type="churn_relance"
```

**Plan expiry** — daily task notifies users whose plan expired:

```python
from app.modules.payment.jobs import expire_individual_plans_task
# Runs daily at 0h15, downgrades to freemium and notifies with template_type="plan_expired"
```

### Referral module (`app.modules.referral`)

**First payment marks filleul active** — when a referred user makes their first payment,
the referral module should mark the referral as active (to unlock parrain rewards):

```python
# After payment complete, the referral module should be notified
# e.g. in validate_subscription_task or via webhook handler:
from app.modules.referral.services import ReferralService
referral_svc = ReferralService(db=db)
referral_svc.mark_filleul_active(user_id)
```

### Core / Quota module (`app.modules.core`)

**Quota check before skill/search** — the `/payment/status` endpoint returns quota info
that other modules should check before allowing IA operations:

```python
from app.modules.payment.routes.dependencies import get_db
from app.modules.payment.models import PlanPrice

db = next(get_db())
plan = db.query(PlanPrice).filter(PlanPrice.plan_id == user.plan_effectif).first()
if plan:
    quota_limit = plan.quota_valeur
    quota_type = plan.quota_type  # "monthly" or "daily"
    # Check against usage counter before allowing skill/search
```

---

## Models

| Model         | Table            | Description                            |
|---------------|------------------|----------------------------------------|
| `Transaction` | `transactions`   | Payments, transfers, full traceability |
| `PlanPrice`   | `plan_prices`    | Plan pricing grid (source of truth)    |

---

## Services

| Service                      | Description                          |
|------------------------------|--------------------------------------|
| `PaymentService`             | Init payments, verify transactions, validate subscriptions |
| `WebhookService`             | HMAC validation, webhook event routing |
| `PaymentAnalyticsService`    | MRR calculation, conversion rates, pending detection |

---

## Scheduled Tasks (Celery Beat)

| Task                        | Frequency            | Description                       |
|-----------------------------|----------------------|-----------------------------------|
| `expire_individual_plans`   | Daily 0h15           | Expire plans, downgrade to freemium |
| `calculate_daily_mrr`       | Daily 1h00           | Calculate and cache MRR           |
| `detect_churn`              | Weekly Sunday 7h     | Find non-renewing users, send relance |

---

## Rate Limits

| Endpoint              | Limit            |
|-----------------------|------------------|
| `POST /checkout`      | 3 requests / 10 min |
| `GET /history`        | 20 requests / 1 min |

---

## NotchPay Configuration

Required environment variables:
- `NOTCH_PUBLIC_KEY` — Public API key
- `NOTCH_SECRET_KEY` — Secret API key
- `NOTCH_PRIVATE_KEY` — Private key for HMAC validation
- `NOTCH_WEBHOOK_HASH_KEY` — HMAC hash key for webhook validation
- `NOTCH_CALLBACK_URL` — Frontend callback URL after payment
- `NOTCH_WEBHOOK_URL` — NotchPay webhook endpoint URL

Plans supported: `freemium`, `access`, `premium`, `pro`, `unlimited`, `school`
