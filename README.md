# DriftGuard

**Schema drift detection engine for data pipelines.** Catches silent data corruption before it reaches your reports and ML models.

## The Problem

| What happened | What you saw | Cost |
|---|---|---|
| Vendor API changed `amount` from int→string | 3 days of NaN revenue reports | $250K misreported |
| DBA added `deleted_at` column | ML model trained on garbage feature | 2 weeks retraining |
| Partner CSV swapped columns | Phone numbers in email field | GDPR violation |

DriftGuard snapshots your upstream schemas and diffs them on every run. It classifies each change as **BREAKING** (will crash) or **SILENT CORRUPTION** (won't crash, will poison data).

## 🚀 Quick Start

```bash
pip install -r requirements.txt

# Take baseline snapshot
python main.py snapshot mydata.db --table users

# Later: check for drift
python main.py check mydata.db --table users

# CSV / JSON sources
python main.py snapshot data.csv
python main.py check data.json

# CI/CD: exit code 2 = breaking, 1 = silent corruption, 0 = clean
python main.py check prod.db -t orders || echo "DRIFT DETECTED"
```

## Exit Codes (CI/CD Integration)

| Code | Meaning | Action |
|------|---------|--------|
| 0 | No drift | Pipeline safe |
| 1 | Silent corruption risk | Review recommended |
| 2 | Breaking change | Block pipeline |

## 💰 Pricing

| Feature | Free | Pro $99/mo | Enterprise $599/mo |
|---|---|---|---|
| Sources | SQLite, CSV, JSON | + Postgres, MySQL, Snowflake, S3 | + Kafka, REST API, custom |
| Schema diff & classification | ✅ | ✅ | ✅ |
| Auto-fix patch generation | ✅ | ✅ | ✅ |
| CI/CD exit codes | ✅ | ✅ | ✅ |
| History & versioning | 10 snapshots | Unlimited | Unlimited |
| Slack / PagerDuty alerts | ❌ | ✅ | ✅ |
| DAG blast-radius analysis | ❌ | ✅ | ✅ |
| Scheduled monitoring (cron) | ❌ | ✅ | ✅ |
| Dashboard & timeline UI | ❌ | ✅ | ✅ |
| SSO / SAML / audit trail | ❌ | ❌ | ✅ |
| Self-hosted option | ❌ | ❌ | ✅ |
| SLA & support | Community | Email | Dedicated |

## 📊 Why Pay?

**One silent corruption incident costs $10K–$500K** in bad decisions, retraining, compliance fines, and engineering time. DriftGuard Pro at $99/mo pays for itself the first time it catches a `INTEGER→TEXT` drift your pandas pipeline would have silently turned into NaN.

ROI: Prevent 1 incident/year = **50–5000x return** on subscription cost.

## License

BSL 1.1 — Free for teams ≤5. Commercial license required for larger teams.
