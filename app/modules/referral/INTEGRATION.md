# Referral Module - Integration Guide

## Overview

The referral module implements a complete parrainage (referral) system where users can invite friends and earn plan upgrades as rewards.

## Directory Structure

```
app/modules/referral/
├── models/           # Database models
│   ├── referral_activity.py   # Tracks referral relationships
│   └── referral_reward.py     # Tracks reward grants
├── utils/            # Utility functions
│   ├── constants.py           # Plan hierarchy, reward tiers
│   ├── referral_code_generator.py  # Code generation/validation
│   └── reward_calculator.py    # Reward plan calculations
├── services/         # Business logic
│   ├── base.py                # Base service with DB/Redis
│   ├── referral_service.py    # Core referral operations
│   ├── qr_code_service.py     # QR code generation
│   └── referral_analytics.py  # Analytics and reporting
├── routes/           # API endpoints
│   ├── dependencies.py        # DI factories
│   ├── referral.py            # User-facing endpoints
│   └── admin.py               # Admin-only endpoints
├── jobs/             # Celery tasks
│   ├── celery_app.py          # Celery configuration
│   ├── tasks.py               # Async tasks
│   └── crons.py               # Beat schedule
├── schemas/          # Pydantic models
│   ├── requests.py            # Request schemas
│   └── responses.py           # Response schemas
└── router.py         # Main router
```

## API Endpoints

### User Endpoints (prefix: `/api/v1/referral`)

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| GET | `/referral/me` | Get my referral stats | Required | - |
| GET | `/referral/check/{code}` | Validate referral code | Public | 20/min |
| GET | `/referral/rewards` | Get reward tiers info | Public | - |
| GET | `/referral/me/qr-code` | Get QR code image | Required | 10/hour |

### Admin Endpoints (prefix: `/api/v1/admin/referral`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/admin/referral/stats` | Global referral stats | Admin |
| GET | `/admin/referral/leaderboard` | Referral leaderboard | Admin |
| POST | `/admin/referral/verify-rewards` | Check/apply pending rewards | Admin |

## Integration Contracts

### Users Module - Registration

When a user registers with a referral code:

```python
# In user_service.inscrire_utilisateur
if referral_code:
    referrer = db.query(User).filter(User.referral_code == referral_code).first()
    if referrer:
        # Referral activity is recorded by the referral module
        from app.modules.referral.services.referral_service import ReferralService
        referral_svc = ReferralService(db=db)
        referral_svc.enregistrer_parrainage(
            referrer_id=str(referrer.id),
            referee_id=str(new_user.id),
            canal="lien_direct",
        )
```

### Search Module - First Search Activation

When a user performs their first search, activate them as a referee:

```python
# In search service after first search
if user.referred_by_id:
    from app.modules.referral.services.referral_service import ReferralService
    referral_svc = ReferralService(db=db)
    referral_svc.marquer_filleul_actif(referee_id=str(user.id))
```

### Payment Module - First Payment Activation

When a user makes their first payment, activate them as a referee:

```python
# In payment callback handler
if user.referred_by_id:
    from app.modules.referral.services.referral_service import ReferralService
    referral_svc = ReferralService(db=db)
    referral_svc.marquer_filleul_actif(referee_id=str(user.id))
```

### Notifications Module

The referral module sends notifications via the notification system. Required notification templates:

- `referral_actif`: Sent to referrer when referee becomes active
  - Params: `referee_prenom` (str)
- `referral_reward`: Sent to referrer when they receive a reward
  - Params: `plan` (str), `cycle` (int)

### Users Module - Plan Updates

When a reward is applied, the `ReferralService` directly updates:
- `User.plan_effectif` → upgraded plan
- `User.plan_expiration_at` → expiration date (30 days from now)

When rewards expire (via Celery task), plans are reverted to `plan_avant`.

## Reward Tiers

| Active Referees | Reward Plan | Duration |
|----------------|-------------|----------|
| 3 | access | 30 days |
| 6 | premium | 30 days |
| 9 | pro | 30 days |
| 12 | unlimited | 30 days |

## Celery Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `notify_referral_active_task` | On-demand | Notify referrer of referee activation |
| `notify_referral_reward_task` | On-demand | Notify referrer of reward received |
| `check_expired_rewards_task` | Every 1 hour | Revert expired reward plans |
| `sync_active_referees_task` | Every 2 hours | Activate dormant referees with activity |

## Database Tables

### `referral_activities`
- Tracks who referred whom
- `is_active` flag (set on first search/payment)
- `canal_acquisition`: source channel
- `recompense_appliquee`: whether reward was counted

### `referral_rewards`
- Tracks plan upgrades granted
- `expiration_at`: when the upgrade expires
- `nb_filleuls_atteint`: the tier threshold (3, 6, 9, 12)

## Setup in main.py

To include the referral router in the application:

```python
from app.modules.referral.router import router as referral_router

app.include_router(referral_router, prefix="/api/v1")
```

## Database Tables Creation

The models will be auto-created if `AUTO_CREATE_DB=True`. In production, use Alembic:

```python
from app.modules.referral.models import ReferralActivity, ReferralReward
# These import registers tables with Base.metadata
```
