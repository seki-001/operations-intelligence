# Architecture

```
 Google Sheet (daily_ops tab)                      Browser
        │  read-only service account                  │  no secrets, no direct API calls
        ▼                                             ▼
 ┌──────────────────────── FastAPI ───────────────┐  ┌──────── Next.js (server) ────────┐
 │ integrations/sources.py  fetch raw rows        │  │ server components + actions      │
 │ services/data_validation.py  reject / flag     │◄─┤ send X-API-Key from server env   │
 │ services/sync.py  snapshot per sync run        │  └──────────────────────────────────┘
 │ services/analytics.py  deterministic metrics   │
 │ services/ai_reporting.py  facts → briefing     │──► OpenAI-compatible LLM (optional)
 │ api/routes.py  REST + API-key auth             │      gets aggregated facts only
 └──────────────┬─────────────────────────────────┘
                ▼
        SQLite (local) / Postgres (production)
        SyncRun · OpsRecord · DataIssue · Report
```

## Data flow

1. **Fetch.** `GoogleSheetsSource` calls the Sheets v4 `values.get` endpoint with the
   `spreadsheets.readonly` scope. Access errors are turned into plain messages people can act on
   ("Share the sheet with the service account email").
2. **Validate.** `validate_rows` checks the header first; if any expected column is missing, the
   whole sync fails. Then each row is checked:
   - *Errors* (row rejected): a missing required value, a non-numeric or negative value, uptime over
     100%, an unparseable or future date, a fractional count, a duplicate site and date.
   - *Warnings* (row kept): energy sold above generation, collections over 150% of billing,
     100% uptime alongside outage events, blank optional counts.
3. **Snapshot.** Valid rows and every issue are stored against a new `SyncRun`. Analytics always read
   the latest *successful* run, so a failed or partial sync never mixes old and new data.
4. **Analyse.** `compare_periods` compares the latest N days with the N days before, per site and for
   the whole portfolio, and applies the thresholds in `THRESHOLDS`. A change in a total is only
   reported when both periods are complete.
5. **Brief.** `build_facts` turns the comparison into numbered facts (P1… for the portfolio,
   F1… for findings). The model receives only these. `check_against_facts` then flags any number in
   the output that isn't in the facts, and any citation to a fact that doesn't exist. The template
   provider produces the same structure without a model and is labelled as not AI-generated.
6. **Review.** Reports start as `pending_review`, and approving or rejecting one records the
   reviewer's name and the time.

## Security and governance

- **Least privilege at the source:** the credential is read-only and the sheet is shared as Viewer.
- **Secrets:** environment variables only; `.env*` and key files are git-ignored. In production the
  API refuses every request if `API_KEY` is not set, rather than allowing unauthenticated access.
- **The browser never holds a credential:** the browser only talks to the Next.js server, which
  calls the API with the server-side key.
- **What the AI sees:** only aggregated site-level facts, with no customer-level records. The
  provider is configurable, so only an approved provider needs to be used.
- **Humans stay in the loop:** briefings are drafts until a named person approves them. The tool
  suggests checks; it never takes action.
- **Small attack surface:** only GET and POST are allowed, CORS is restricted to the dashboard's
  origin, interactive API docs are off in production, the container runs as a non-root user, and
  basic security headers are set on the dashboard.

## Authentication to Google without stored keys

Google now blocks downloadable service-account keys by default for new organisations
(`iam.disableServiceAccountKeyCreation`), and this demo ran into that policy. For a real deployment, the
API should run on Google Cloud (e.g. Cloud Run) **under an attached service account**. The code then
picks up its credentials automatically and no key file exists to leak or rotate. Outside Google Cloud,
**Workload Identity Federation** gives the same result. The demo supports a key (`google_sheets`) and a
link-shared sheet (`google_sheets_link`, demo data only) so it can be run anywhere.

## What would change for a real deployment

| Area | Demo | Production |
|---|---|---|
| Users | Shared API key between the two servers | Google Workspace sign-in, role-based access, audit log |
| Database | SQLite or a free Postgres | Managed Postgres with automated backups and tested restores |
| Scheduling | "Sync now" button | Scheduled sync, with alerts on failure or when rejected rows exceed a threshold |
| Thresholds | Constants in code | Owned and tuned by operations/FP&A, stored as configuration |
| Monitoring | `/health` | Uptime checks, error tracking, structured logs, availability target |
| Environments | One | Separate dev/staging/production, with secrets in a secrets manager |
