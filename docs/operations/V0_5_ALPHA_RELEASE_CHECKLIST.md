# v0.5.0a1 experimental dashboard milestone — candidate gate

**Status: planning / not published (2026-10-17).** This is a new milestone,
not a retroactive change to the published [v0.4.0a1](https://github.com/Monotoba/UniversalDDNSServer/releases/tag/v0.4.0a1)
release. Do not interpret checked development items as release approval.

## Candidate definition
- [x] Merge dashboard foundation, recent history, filtering, per-record details, and read-only authoritative observation (PRs #164–#168).
- [ ] Independently review feature diff, dependencies, README, implementation plan, feature guides, and release notes.
- [ ] Advance `pyproject.toml` and FastAPI metadata from 0.4.0a1 to 0.5.0a1 in a **separate explicitly reviewed candidate PR**.
- [ ] Freeze exact candidate commit and tag target. No tag or release is authorized yet.

## Automated candidate verification
- [ ] Pass static quality, unit and documentation tests, BIND/SQLite integration (Python 3.11, 3.12, 3.13), operator fixture and release candidate packaging **at the frozen candidate SHA**.
- [ ] Inspect new dashboard tests in each Python matrix log, including unauthorized record rejection, no DNS write, backend-failure `unavailable`, bounded filtering and runtime observer hookup.
- [ ] Verify wheel and sdist metadata, license inclusion (PEP 639), included modules, secret exclusion and SHA-256 values from the actual frozen candidate build.
- [ ] Document any differences between the reviewed code SHA, packaged artifact hashes and final immutable tag.

## Disposable VM verification (not performed in this milestone)
- [ ] Verify guest identity, isolation, approved backup, and clean lab baseline.
- [ ] Upgrade only after a **separate explicit authorization**; record exact pre- and post-upgrade Git SHAs and backup path.
- [ ] Verify dashboard loads via loopback and authenticated read-only discovery/record details/history.
- [ ] Use isolated BIND test RRset to confirm actual authoritative observation result, mismatches, absent record and timeout or error `unavailable`.
- [ ] Verify inactive and unauthorized record IDs are hidden, writes are not possible with read-only token, and no unintended DNS writes occur.
- [ ] Exercise a guarded rollback and verify restored application-level behavior; mere service activation is not disaster-recovery proof.

## Security and release authorization
- [ ] Reassess loopback/browser-origin assumptions, privileged operator broker, SQLite direct write permissions, token lifetime in browser memory and TSIG credential exposure in API runtime.
- [ ] Confirm no public HTTPS, delegated RBAC, distributed rate limiting, or production security claim is made.
- [ ] Prepare draft release notes, compare with implementation plan and changelog, and obtain explicit approval for tag/artifact publication.
- [ ] Independently verify GitHub prerelease state, tag SHA, assets and SHA-256 checksums **after** publication, if approved.

## Current evidence and limitations
- PRs #164–#168 were squash-merged after their five exact-head workflow checks passed; tests exercised on Python 3.11–3.13.
- The local dashboard cannot edit records or administer credentials. `GET /api/v1/intents` lists only the authenticated principal's currently visible record updates, and counts describe at most the displayed 20 results.
- The API runtime now wires read-only RFC 2136 observation to record details, but the dashboard has not been exercised against the user's live lab VM at this revision. DNS result labels refer to template equality, not a specific intent's success.
- The last published release remains v0.4.0a1 and current package/API metadata remain 0.4.0a1.
