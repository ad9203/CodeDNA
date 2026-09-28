# CodeDNA External Services Connection Guide

This guide details how to configure GitHub, Hindsight Cloud, and Groq.

---

## 1. GitHub Connection

### Option A: Fine-Grained Personal Access Token (Hackathon Fast Path)
1. In GitHub, go to **Settings > Developer Settings > Personal Access Tokens > Fine-grained tokens**.
2. Select your repository.
3. Grant permissions:
   - **Pull requests**: Read and write
   - **Issues**: Read and write (for comment feedback)
   - **Contents**: Read
4. Set token in `.env`:
   ```env
   GITHUB_TOKEN=github_pat_...
   ```

### Webhook Setup
1. In your repository, go to **Settings > Webhooks > Add webhook**.
2. **Payload URL**: `https://<tunnel-domain>/api/webhook/github`
3. **Content type**: `application/json`
4. **Secret**: generate a secure random string and set as `GITHUB_WEBHOOK_SECRET=...`
5. Select events:
   - Pull requests
   - Pull request reviews
   - Pull request review comments
   - Issue comments

---

## 2. Hindsight Cloud Connection

1. Sign up at [Hindsight Cloud](https://hindsight.vectorize.io).
2. Obtain your API Key and Base URL.
3. Configure `.env`:
   ```env
   HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
   HINDSIGHT_API_KEY=hs_...
   HINDSIGHT_BANK_PREFIX=codedna
   ```

---

## 3. Groq Connection

1. Sign up at [Groq Console](https://console.groq.com).
2. Create an API key.
3. Configure `.env`:
   ```env
   GROQ_API_KEY=gsk_...
   GROQ_MODEL=openai/gpt-oss-120b
   ```

---

## 4. Smoke-Test Execution Order

1. Backend Health: `GET /health/live` & `GET /health/ready`
2. Database Verification: Check SQLite/Postgres tables created
3. Hindsight Healthcheck: Verify bank access and token budget
4. Groq Connectivity: Run schema validation test
5. Webhook Signature Validation: Test with synthetic HMAC signature
6. End-to-end PR Review: Review synthetic fixture
