---
name: http-csrf-session-auditor
description: Audits HTTP route handlers, session configurations, SameSite cookie attributes, and anti-CSRF token middleware across polyglot backend applications (Express/Node.js, PHP, GraphQL) to identify cookie-based authentication reliance and missing CSRF protections.
---

# HTTP Session & CSRF Security Auditor

This skill provides a systematic procedure for inspecting HTTP controllers, route handlers, and middleware to verify whether state-changing operations rely on ambient cookie-based authentication, check `SameSite` cookie security attributes, and identify missing anti-CSRF protection.

---

## Audit Checklist

When auditing a codebase for session and CSRF security, verify the following three core security pillars:

### 1. Authentication Credentials in State-Changing Requests (POST, PUT, DELETE, PATCH)
- **Header-Based Auth (JWT Bearer / API Keys):**
  - Check if auth middleware inspects `req.headers.authorization` (e.g. `Bearer <token>`).
  - **Verdict:** Inherently immune to standard CSRF because browsers do not automatically send custom HTTP authorization headers on cross-site requests.
- **Cookie-Based Auth (Session IDs / Refresh Tokens in Cookies):**
  - Check if routes inspect `req.cookies`, `req.session`, or `Set-Cookie` headers.
  - **Verdict:** Requires CSRF defense (anti-CSRF tokens, SameSite restrictions) because browsers automatically attach ambient domain cookies to cross-site requests.

### 2. Cookie Security Attributes Configuration
If cookie-based auth or session management is used, inspect the session configuration or cookie serializer for:
- **`SameSite` Attribute:** Must be set to `Lax` or `Strict`.
- **`HttpOnly` Flag:** Prevents client-side JavaScript access (`document.cookie`), mitigating XSS-based session hijacking.
- **`Secure` Flag:** Ensures cookies are transmitted strictly over HTTPS.

### 3. Anti-CSRF Token Middleware
Check whether explicit CSRF protection is active for state-changing routes:
- **Middleware Presence:** Search for `csurf`, `csrf-sync`, `double-submit-cookie`, or custom anti-CSRF middleware.
- **Exemptions / Webhooks:** Webhook endpoints (e.g., Shopify, Stripe) should be exempt from standard session CSRF tokens and instead validated via HMAC signature headers (e.g., `X-Shopify-Hmac-SHA256`).
- **Unauthenticated Endpoints:** Public POST endpoints (login, register) consume JSON bodies and rate limiting, so CSRF is typically not applicable unless session cookies are initiated prior to login.

---

## Step-by-Step Audit Workflow

1. **Locate Server Entrypoint & Route Registrations:**
   - Scan server entrypoints (e.g., `src/index.ts`, `server.js`, `routes/`).
   - Identify active session or cookie parser middleware (`express-session`, `cookie-parser`).

2. **Inspect Auth Middleware:**
   - Search for authentication handlers and extract how user identity is established.
   - Verify whether state-changing HTTP methods (`POST`, `PUT`, `DELETE`) require bearer tokens or session cookies.

3. **Check Token & Cookie Issuance:**
   - Examine login/auth controller actions (`AuthController`, login routes).
   - Check if login responses return tokens in the JSON response body or set `Set-Cookie` headers.

4. **Synthesize Security Report:**
   - Report findings categorized by:
     - Reliance on cookie-based authentication (Yes/No/N/A).
     - SameSite cookie configuration (Lax/Strict/None/Missing).
     - Presence or necessity of anti-CSRF token middleware.
