# v0.2.0a1 — fixed experimental alpha milestone

**Status:** Development; not yet tagged or released. This document defines a bounded plan, not a production-readiness claim.

## Objective
Provide a diagnosable, safely operable local DDNS control plane while preserving the released v0.1.0a1 baseline. No new authoritative server, internet-facing deployment, or general automatic uncertain-result retry is planned.

## Completed foundation (as of 2026-10-14)
- Local operator journal `list`, `show`, and observe-only `reconcile`
- Structured API, publishing and recovery events, with redaction and journald guidance
- VM updater with offline SQLite snapshot, startup readiness wait, best-effort rollback, and non-mutating `--verify`
- Isolated CI for Python 3.11–3.13 and real BIND 9 integration

## Remaining tracked deliverables (priority order)
1. [#1 Safe operator recovery](https://github.com/Monotoba/UniversalDDNSServer/issues/1): finalize controlled recovery workflows and tests; no blind retry.
2. [#2 Credential lifecycle](https://github.com/Monotoba/UniversalDDNSServer/issues/2): secure local metadata inspection, token rotation, and revocation semantics.
3. [#3 Versioning and release gate](https://github.com/Monotoba/UniversalDDNSServer/issues/3): `0.2.0a1` metadata, auditable packaging, stable release notes, and owner-approved tag/release.

## Frozen release acceptance
- All three deliverables above are closed or explicitly deferred in release notes with the owner's approval.
- Existing CI static, unit/docs, and BIND 9 integration must pass at the release commit; artifact metadata and checksums must be checked.
- No additional mandatory VM scenarios beyond a basic existing-install health check; genuinely unverified crash behavior is explicitly disclosed.
- Rollback is best effort. A Git revision is not automatically a released package version.
- A final owner approval is required before publishing.

## Deferred beyond v0.2.0a1
Production TLS and internet exposure, distributed throttling, HA, authoritative DNS hosting, cross-writer compare-and-swap, guaranteed exactly-once DNS publication, and full disaster-recovery certification.

## Process
New findings are logged as issues. They do not change this release gate unless an actual security or data-loss blocker is demonstrated. Separate follow-up enhancements from release prerequisites.

## Issue #1 implementation note

Operator recovery now returns distinct process exit statuses: `0` successful operation/verified reconciliation, `3` missing intent, `4` invalid state or authorization refusal, `5` DNS observation unavailable, and `6` observation succeeded but RRset still differs (left unresolved). Standard JSON is emitted for a successful observation, including the unresolved result; diagnostic errors go to stderr. Reconciliation is **observation-only** and will not retry writes. Operator permissions remain restricted to the local service account. This change does not imply the complete issue is closed until the remaining acceptance criteria have been checked.

## Milestone tracking update (2026-10-14)

- [x] [Issue #1](https://github.com/Monotoba/UniversalDDNSServer/issues/1) operator recovery completed: bounded inspection, observe-only reconciliation, distinct error statuses and regression coverage; the full static/unit/integration CI suite passed.
- [ ] [Issue #2](https://github.com/Monotoba/UniversalDDNSServer/issues/2) credential lifecycle begun with a local `python -m universalddns.admin --config CONFIG list` command. It displays principal, scopes, managed record IDs and revocation status, never bearer tokens or digest values. Rotation documentation and revocation test review remain.

## Credential rotation operating procedure

Issue a replacement credential with identical least-privilege scopes, transfer it securely to the client, verify that it authenticates, and only then revoke the old credential through the local admin command using `--token-stdin`. Issue and revoke are local administrative operations; never put bearer values on the command line or in Git. List credential metadata with `python -m universalddns.admin --config CONFIG list`. The inventory deliberately hides token identifiers and hashes, so keep a secure external issuance record to distinguish credentials for the same principal. Revocation of the last eligible credential prevents pending publication at the worker authorization check, but does not cancel an update already in flight. Replacing a token does not revoke the old one automatically.
