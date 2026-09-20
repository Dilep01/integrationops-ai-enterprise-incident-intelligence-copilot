---
document_id: oauth-authentication-guide
version: 3.2
effective_from: 2026-07-01
system: bank-api
environment: production
tenant_id: demo-enterprise
allowed_roles: integration-engineer,support-engineer
---

# OAuth Authentication Guide

## Section 7: Token generation after secret rotation

After a client secret is rotated, all new OAuth access tokens must be generated with the active secret version. Tokens generated with the previous secret are rejected by the Bank API with HTTP 401. Confirm the active secret version before requesting a replacement token. Never record the client secret or access token in logs.
