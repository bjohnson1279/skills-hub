---
name: ssrf-outbound-request-auditor
description: Audits polyglot backend applications (Node.js, Express, PHP, Python, GraphQL) for outbound HTTP request patterns (fetch, axios, Guzzle, curl, httpx) consuming user-supplied URLs or hostnames, verifying IP/URL validation controls against SSRF (Server-Side Request Forgery) to local interfaces, private IP ranges, and cloud metadata endpoints.
---

# SSRF & Outbound HTTP Request Security Auditor

This skill provides a structured methodology for auditing polyglot codebases to identify outbound HTTP/HTTPS request mechanisms, analyze whether user inputs influence target destinations, and verify defenses against Server-Side Request Forgery (SSRF).

---

## Security Audit Checklist

When inspecting a codebase for SSRF risks in outbound HTTP calls, evaluate the following three core security dimensions:

### 1. Detection of Outbound Request Mechanisms
Identify all functions, libraries, or network clients capable of initiating HTTP/HTTPS requests:
- **Node.js / TypeScript:** `fetch`, `axios`, `http.request`, `https.request`, `got`, `node-fetch`, `superagent`.
- **PHP:** `curl_exec`, `file_get_contents`, `fsockopen`, `GuzzleHttp\Client`, `Http::get` (Laravel).
- **Python:** `requests`, `httpx`, `urllib.request`, `aiohttp`.

### 2. User Input Influence & Target Analysis
Determine if the outbound request URL, hostname, or IP address can be supplied or manipulated by end users:
- **Dynamic User Inputs:** Webhook registration endpoints, remote image URL downloads, RSS/feed fetchers, PDF generator parameters, proxy endpoints, API connector configurations.
- **Static / Server-Configured Targets:** Third-party API connectors (e.g. Shopify, Stripe, QuickBooks) or internal microservices configured via environment variables (e.g., `SHOPIFY_STORE_DOMAIN`, `DATABASE_URL`).
  - *Verdict:* Server-configured static integrations do not pose user-exploitable SSRF, provided user input cannot override the base domain or path host.

### 3. Verification of SSRF Safeguards & IP Range Validation
If dynamic user-provided URLs or hostnames are consumed, verify if URL validation and IP pinning are implemented prior to initiating network calls:
- **Forbidden IP Ranges to Block:**
  - **Loopback:** `127.0.0.0/8`, `::1`
  - **Private / RFC 1918:** `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
  - **Link-Local / Cloud Metadata:** `169.254.169.254`, `169.254.0.0/16`, `fe80::/10`
  - **Carrier-Grade NAT & Broadcast:** `100.64.0.0/10`, `0.0.0.0/8`, `255.255.255.255/32`
- **DNS Rebinding Protections:** DNS resolution must happen before validation, and the request must be bound to the validated IP address to prevent Time-of-Check to Time-of-Use (TOCTOU) DNS rebinding attacks.

---

## Step-by-Step Audit Workflow

1. **Scan Codebase for Outbound HTTP Client Call Sites:**
   - Run pattern searches (grep/ripgrep) for HTTP client methods across all source files (`*.ts`, `*.js`, `*.php`, `*.py`).
   
2. **Trace Request Parameters to Source Inputs:**
   - For every identified HTTP invocation, trace where the URL, hostname, or parameters originate.
   - Separate server-side configuration (env variables, static configs) from user-controlled request bodies, query params, or path params.

3. **Inspect Existing Validation & Sanitization Helpers:**
   - Look for URL parser usage (`new URL()`, `parse_url()`, `urllib.parse`) and IP validation functions.
   - Verify if validation checks DNS resolution against forbidden IP ranges before execution.

4. **Synthesize Findings & Remediation Plan:**
   - Report findings categorized by:
     - Identified outbound HTTP call sites.
     - Origin of target URLs (User-supplied vs. Server-configured).
     - Presence and effectiveness of SSRF protections.
