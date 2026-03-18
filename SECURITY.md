# Security Policy

## Scope

This repository is an early local-first OSS project. It is not positioned as a hardened hosted service.

Supported versions: only the latest `main` branch and the latest tagged OSS MVP release are considered in scope for fixes.

Please report:

- credential exposure
- unsafe file handling
- command execution issues
- state corruption issues with clear reproduction
- unsafe defaults that could surprise users

## Reporting

Preferred path:

- use GitHub private vulnerability reporting / repository security advisories if the repository UI exposes it

Fallback path:

- if private reporting is unavailable, contact the repository owner through GitHub profile contact options and do not publish exploit details publicly

Public issues are acceptable only for low-detail coordination messages that avoid exploit steps, credentials, or proof-of-concept payloads.

## Response Expectations

- initial acknowledgement target: within 7 days
- triage target for reproducible reports: within 14 days
- fix timing depends on severity, maintainership availability, and whether the issue fits the documented local-first scope

This repository is maintained as an OSS MVP. Best-effort handling is the expectation; there is no enterprise SLA.

## Expected Boundaries

Current non-goals:

- internet-facing production hardening
- auth and tenant isolation
- secret management for hosted deployments

Please keep reports focused on the current documented local-first scope.
