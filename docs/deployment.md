# Deployment

The cheapest working setup is the **API on Render** (Docker, free plan), the **dashboard on Vercel**,
and optionally a **free Neon Postgres** database. Expect about 45 minutes the first time.

## 1. Google Sheet + service account (read-only)

1. Create a Google Sheet. Rename the first tab to **`daily_ops`**, then *File → Import →
   Upload* `data/synthetic_daily_ops.csv` and choose *Replace current sheet*.
2. In the [Google Cloud console](https://console.cloud.google.com), create a project and enable the
   **Google Sheets API** (*APIs & Services → Library*).
3. Go to *IAM & Admin → Service accounts → Create*. It needs **no project roles**.
4. Open the service account, go to *Keys → Add key → JSON*, and download the file. **Treat it as a
   password: don't email it and don't commit it.**
5. Back in the sheet, *Share* it with the service account's email (`…@….iam.gserviceaccount.com`)
   as **Viewer**.
6. Copy the sheet ID from its URL: `docs.google.com/spreadsheets/d/<THIS_PART>/edit`.

### Alternative: no Google Cloud project (shared-link mode)

If you can't create a service-account key (for example, your Workspace organisation blocks key creation, or
your account has hit its project quota), share the sheet as **Anyone with the link: Viewer** and set:

```
DATA_SOURCE=google_sheets_link
GOOGLE_SHEET_ID=<sheet id>
GOOGLE_SHEET_GID=<number after #gid= in the URL, often 0>
```

The app reads the sheet's CSV export, so no credentials are involved, but **anyone with the link can read
the sheet**. That's acceptable for this synthetic demo and not for real data.

To test the service-account mode locally, set these in `backend/.env`:

```
DATA_SOURCE=google_sheets
GOOGLE_SHEET_ID=<sheet id>
GOOGLE_SERVICE_ACCOUNT_FILE=/absolute/path/to/key.json
```

## 2. AI provider (optional)

Without a key the briefing uses the labelled template. To use a model, create a key with any
provider that has an OpenAI-compatible API, for example:

| Provider | AI_BASE_URL | Example AI_MODEL |
|---|---|---|
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| Google AI Studio | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.0-flash` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.2` |

Model names change over time, so check the provider's current model list. Then set
`AI_PROVIDER=openai_compatible` and `AI_API_KEY`.

## 3. Database (recommended for a hosted demo)

Render's free disk is wiped on every redeploy. Create a free Postgres database on
[Neon](https://neon.tech) and use its connection string in this form:
`postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`.
(Without one the demo still works, but you'll need to click "Sync now" after each restart.)

## 4. API and dashboard on Render

1. Push the repository to GitHub.
2. In Render, go to *New → Blueprint* and pick the repository; it reads `render.yaml`, which defines
   both the API and the dashboard. The dashboard reads the API key from the API service, so the key
   is never copied by hand.
3. Fill in the secret values when prompted (or use Render's *Generate* for `API_KEY`):
   - `DATABASE_URL`: from Neon, or `sqlite:///./operations_intelligence.db` for a throwaway demo
   - `GOOGLE_SHEET_ID`
   - `AI_API_KEY` (optional)
4. Check that `https://<your-api>.onrender.com/health` returns `{"status":"ok"}`.

Free Render services go to sleep when idle, so the first request after a while takes about 30–60
seconds. Open the dashboard once before sharing the link. (Vercel works too for the dashboard: set the
root directory to `frontend` and add `API_URL` and `API_KEY` as server-side variables.)

## Rollback

- **Render:** *Events → choose the previous deploy → Rollback*.
- **Data:** every sync is its own snapshot, so a bad sheet edit doesn't destroy history. Fix the sheet
  and sync again.

## Checks before sharing

- [ ] `/health` returns OK
- [ ] The dashboard shows "Google Sheets (link)" as the source in the top bar
- [ ] The data-quality panel lists the deliberate demo errors
- [ ] A briefing can be drafted and approved
- [ ] No secrets in the repository: `git grep -iE "private_key|api_key=.+"` returns nothing
