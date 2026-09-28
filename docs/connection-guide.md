# CodeDNA External Services Connection & Deployment Guide

This comprehensive guide details step-by-step procedures for configuring external connections (GitHub, Hindsight Cloud, Groq), provisioning local and cloud databases, configuring secure webhooks and tunnels, deploying to production (Railway + Vercel), enforcing strict CORS, and executing the mandatory 9-step connection smoke-test sequence.

---

## 1. GitHub Connection (Section 20.1)

CodeDNA requires access to pull request diffs, metadata, and review submission endpoints.

### Option A: Fine-Grained Personal Access Token (Hackathon Fast Path)
Best for quick hackathon setup and local evaluation.

1. Navigate to **GitHub > Settings > Developer Settings > Personal Access Tokens > Fine-grained tokens**.
2. Click **Generate new token**.
3. Under **Repository access**, select **Only select repositories** and pick your target test repository (e.g., `codedna-sandbox`).
4. Under **Permissions**, grant the following minimum required privileges:
   - **Pull requests**: Read and write (to fetch PR metadata, diffs, and submit inline reviews)
   - **Contents**: Read-only (to inspect source files if required)
   - **Issues**: Read and write (optional, for PR comment thread tracking)
5. Generate the token and store it in `backend/.env`:
   ```env
   GITHUB_TOKEN=github_pat_11...
   ```

### Option B: GitHub App (Preferred Enterprise Path)
Best for multi-tenant production deployments with short-lived installation access tokens.

1. Navigate to **GitHub > Settings > Developer Settings > GitHub Apps > New GitHub App**.
2. Configure App settings:
   - **GitHub App name**: `CodeDNA-Reviewer`
   - **Homepage URL**: `https://your-domain.com`
   - **Webhook URL**: `https://<your-tunnel-or-domain>/api/webhook/github`
   - **Webhook secret**: Secure random string (e.g. `openssl rand -hex 24`)
3. Set Repository Permissions:
   - **Pull requests**: Read & write
   - **Contents**: Read-only
   - **Metadata**: Read-only
4. Subscribe to Webhook Events:
   - Pull request
   - Pull request review
   - Pull request review comment
   - Issue comment
5. Generate a private key (`.pem` format) and download it securely.
6. Install the App onto your organization or repository, note the `Installation ID`, and set in `backend/.env`:
   ```env
   GITHUB_APP_ID=123456
   GITHUB_INSTALLATION_ID=7891011
   GITHUB_PRIVATE_KEY_PATH=/path/to/private-key.pem
   ```
   *Note: `GitHubAuthProvider` abstracts token retrieval so the review orchestrator functions identically under both PAT and App auth.*

### Webhook Subscription Configuration
In your repository's **Settings > Webhooks > Add webhook**:
- **Payload URL**: `https://<public-domain-or-tunnel>/api/webhook/github`
- **Content type**: `application/json`
- **Secret**: Must match `GITHUB_WEBHOOK_SECRET` in `backend/.env`
- **SSL verification**: Enable SSL verification
- **Selected events**:
  - `Pull requests` (triggers review on `opened` and `synchronize`)
  - `Pull request reviews` (triggers learning on human approval/changes requested)
  - `Pull request review comments` (captures inline human feedback)
  - `Issue comments` (captures reviewer feedback commands)

---

## 2. Hindsight Connection (Section 20.2)

Hindsight provides persistent, cross-PR organizational memory that stores team conventions, architectural guidelines, postmortem learnings, and negative constraints from human reviewer feedback.

1. **Sign Up**: Register at [Hindsight Cloud](https://hindsight.vectorize.io).
2. **Promotional Credits**: Apply promo code **`MEMHACK99`** in the Hindsight Cloud billing/credit settings for hackathon credits.
3. **Memory Bank Provisioning**:
   - CodeDNA partitions banks per repository: `codedna:{owner}:{repo}`.
   - Banks are automatically initialized on first recall/retain if they do not yet exist.
4. **Structured LLM Configuration**:
   - Ensure the Hindsight service configuration is set to use a structured-output capable LLM (such as GPT-4o or Claude 3.5 Sonnet) for memory consolidation.
5. **Configure `backend/.env`**:
   ```env
   HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
   HINDSIGHT_API_KEY=hs_...
   HINDSIGHT_BANK_PREFIX=codedna
   HINDSIGHT_RECALL_BUDGET=mid
   HINDSIGHT_MAX_RECALL_TOKENS=4096
   ```

*Resilience note: If Hindsight is temporarily unreachable, CodeDNA logs a warning and gracefully degrades to stateless review without dropping or failing the pull request review.*

---

## 3. Groq Connection (Section 20.3)

Groq provides ultra-fast inference for generating structured pull request reviews adhering to strict Pydantic schemas.

1. **Sign Up**: Create an account at [Groq Console](https://console.groq.com).
2. **API Key**: Generate an API key under **API Keys**.
3. **Model Selection**:
   - CodeDNA defaults to `openai/gpt-oss-120b`, offering high-context reasoning and strict JSON mode output.
   - Alternative supported models: `llama-3.3-70b-versatile` or `mixtral-8x7b-32768`.
4. **Configure `backend/.env`**:
   ```env
   GROQ_API_KEY=gsk_...
   GROQ_MODEL=openai/gpt-oss-120b
   GROQ_TEMPERATURE=0.0
   GROQ_MAX_TOKENS=6000
   ```

*Security note: `GROQ_API_KEY` is loaded as a `SecretStr` and is strictly forbidden from appearing in logs, error payloads, or frontend builds.*

---

## 4. Local Database (Section 20.4)

CodeDNA persists review lifecycle states, raw PR metadata, recalled memory snapshots, generated findings, and human feedback audit trails across 7 relational tables.

### Local Development (SQLite with aiosqlite)
Zero-configuration local database:
```env
DATABASE_URL=sqlite+aiosqlite:///./codedna.db
```
Initialize migrations:
```bash
cd backend
alembic upgrade head
```

### Production Deployment (PostgreSQL with asyncpg)
Production multi-worker database:
```env
DATABASE_URL=postgresql+asyncpg://postgres:secure_password@postgres.railway.internal:5432/railway
```
Run migrations against the target database:
```bash
alembic upgrade head
```
*Isolation note: Never share database instances between test/mock runs and production.*

---

## 5. Local Webhook Tunnel (Section 20.5)

GitHub webhook delivery requires a publicly accessible HTTPS endpoint during local development.

### Option A: Cloudflare Tunnel (Recommended — Free & Stable)
```bash
# Install cloudflared, then run:
cloudflared tunnel --url http://localhost:8000
```
Copy the assigned `https://<unique-id>.trycloudflare.com` URL.

### Option B: ngrok
```bash
ngrok http 8000
```
Copy the assigned forwarding URL `https://<unique-id>.ngrok-free.app`.

### Webhook Endpoint
Update your GitHub repository webhook URL to:
```text
https://<tunnel-domain>/api/webhook/github
```

---

## 6. Backend Deployment — Railway (Section 20.6)

1. Create a project in [Railway](https://railway.app).
2. Provision a **PostgreSQL** database service.
3. Add a **New Service** connected to your GitHub repository, pointing to the root directory with backend Dockerfile or Python buildpack:
   - Root directory: `/backend` (or use root `Dockerfile`)
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Set Environment Variables in Railway:
   ```env
   ENVIRONMENT=production
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   FRONTEND_ORIGIN=https://codedna-frontend.vercel.app
   BACKEND_PUBLIC_URL=https://codedna-backend.up.railway.app
   GITHUB_TOKEN=...
   GITHUB_WEBHOOK_SECRET=...
   GROQ_API_KEY=...
   HINDSIGHT_API_KEY=...
   HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
   GROQ_MODEL=openai/gpt-oss-120b
   LOG_LEVEL=INFO
   ```
5. Run migrations via Railway CLI or one-off deployment command:
   ```bash
   alembic upgrade head
   ```

---

## 7. Frontend Deployment — Vercel (Section 20.7)

1. Import your GitHub repository into [Vercel](https://vercel.com).
2. Configure project settings:
   - **Framework Preset**: Next.js
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `.next`
3. Configure Environment Variables:
   ```env
   NEXT_PUBLIC_API_BASE_URL=https://codedna-backend.up.railway.app/api
   ```
4. Deploy the application and note the assigned production domain (e.g., `https://codedna.vercel.app`).

---

## 8. CORS Configuration (Section 20.8)

Cross-Origin Resource Sharing is strictly locked to prevent unauthorized cross-site requests.

- **Local Development**:
  ```env
  FRONTEND_ORIGIN=http://localhost:3000
  ```
- **Production**:
  ```env
  FRONTEND_ORIGIN=https://codedna.vercel.app
  ```

> [!CAUTION]
> Never set `FRONTEND_ORIGIN=*` or use wildcard origins in production. CodeDNA's settings validator automatically rejects wildcard origins in `production` mode with a fatal startup error.

---

## 9. Mandatory Connection Smoke-Test Order (Section 20.9)

Execute this exact 9-step verification sequence to validate the end-to-end integration:

```bash
# From workspace root:
python scripts/verify_connections.py
```

### The 9 Verification Steps:
1. **Backend Health Check**: Verifies `GET /health/live` returns HTTP 200 `{"status": "alive"}`.
2. **Database Connection**: Verifies `GET /health/ready` dynamically connects to SQLAlchemy and confirms tables exist.
3. **Hindsight Connection**: Verifies bank partition `codedna:{owner}:{repo}` accessibility and token budget query.
4. **Groq Connection**: Validates Groq API authentication and JSON-mode structured response adherence.
5. **GitHub Token/App Connection**: Validates authentication provider and repository access permissions.
6. **GitHub Webhook Signature Validation**: Validates constant-time HMAC-SHA256 signature verification over raw payloads.
7. **Test PR Review (Sandbox/Fixture)**: Simulates PR intake and executes diff extraction with bounds checking.
8. **Frontend API Connection**: Validates CORS headers and `/api/stats/overview` endpoint reachability.
9. **End-to-End Live Review**: Executes full loop (`recall -> review -> publish -> feedback -> retain`) and verifies relational audit records.
