# Controlled v0.4 live catalog publication — disposable VM only

This optional test **writes the installed service SQLite database and isolated authoritative DNS**. It is **not** the existing scratch-only CLI fixture. Do not run without a restorable, independently verified VM snapshot and a protected SQLite backup.

## Preconditions (do not automate or assume)

1. Confirm the guest hostname is `uddns-prealpha`, its active zone is `lab.invalid.`, and services listen only on loopback. The scripted test enforces these identities and refuses a preexisting catalog fixture or nonempty DNS name.
2. Preserve a **powered-off** snapshot or full VM disk backup before changing database or BIND policy. The guarded updater backup is not a substitute. Record your snapshot identifier.
3. The operator account must be a direct non-root member of `universalddns-operators`, and must pass `check-operator-readiness.sh`.
4. Operators need scoped write access to SQLite state **and directory for journal/WAL**. Existing ACLs only grant `r-x` on `/var/lib/universalddns`; don't assume the test can write yet. For this disposable VM, review existing ACLs and (only if approved) grant the operator group `rwx` on this directory. The existing named-group ACL on `state.sqlite3` is already `rw-`. Do not grant world access. A stronger design for production would use a mediated admin service rather than writable service state.
5. Inspect `/etc/bind/named.conf.local`. The initial VM installation grants `uddns-lab.` permission only for `home.lab.invalid.`. The test needs a *separate named permission* for `catalog-live.lab.invalid.` A. Back up BIND configuration first, then extend the existing `update-policy` with `grant uddns-lab. name catalog-live.lab.invalid. A;`, retaining the original rule. Validate with `sudo named-checkconf -z` before any controlled `sudo systemctl reload named`. Do **not** use `zonesub`, `wildcard`, or an unrestricted grant. This is an explicit change to your lab's DNS write authority; the test does not modify policy itself.
6. Keep `/etc/universalddns/tsig.json` mode 0600 and inaccessible to operators. The script does not read TSIG.
7. Do not test on a shared zone or a deployed/production service. Ensure `catalog-live.lab.invalid.` does not already exist; the test will refuse an existing RRset.

## Read-only inspection before any changes

From the laptop, with `VM_IP` resolved using `sudo virsh domifaddr uddns-prealpha`:

```sh
ssh ubuntu@"$VM_IP" 'hostname; id -nG; bash /opt/universalddns/src/tests/deployment/check-operator-readiness.sh'
ssh ubuntu@"$VM_IP" 'sudo getfacl -p /var/lib/universalddns /var/lib/universalddns/state.sqlite3; sudo grep -A8 "zone \"lab.invalid\"" /etc/bind/named.conf.local'
ssh ubuntu@"$VM_IP" 'dig +noall +answer @127.0.0.1 catalog-live.lab.invalid A'
```

Inspect these results, snapshot the VM and separately approve scoped filesystem/BIND changes before proceeding.

## Execute after all preconditions

Run as the actual operator login (no sudo, no service account impersonation):

```sh
ssh ubuntu@"$VM_IP" '/opt/universalddns/venv/bin/python /opt/universalddns/src/tests/deployment/check-live-catalog-publication.py --confirm-lab-write'
```

Expected final success signal:

```text
PASS: active catalog -> scoped REST -> worker -> authoritative BIND A
Cleanup: record deactivated
Cleanup: test credential revoked
Note: DNS RRset and inactive catalog fixture remain; no DNS deletion.
```

The script creates `catalog-live-v04`, activates it, issues a scoped temporary bearer (kept out of stdout), discovers the record through the running API, queues its address, polls for worker completion and verifies authoritative BIND. It then attempts deactivation and revocation. If it fails partway through, review stderr and credential blockers rather than blindly retrying: it deliberately refuses reuse of an existing catalog fixture and retains DNS state for evidence. Successful HTTP 202 alone is insufficient. The test does not prove live revocation during an in-flight DNS network request, rollback, production TSIG policy, or multihost conflict semantics.

## Cleanup and evidence

The DNS `catalog-live.lab.invalid.` A RRset is intentionally left in the isolated BIND zone; catalog record remains inactive in SQLite for auditability. The dedicated BIND permission must be removed when testing is complete, after snapshot/evidence review. Do not delete or reuse the fixture blindly. Log commit SHA, VM snapshot, sanitized CLI output, and authoritative observation without including bearer tokens or the TSIG secret. Restore the pretest snapshot if you need an exactly clean test VM.
