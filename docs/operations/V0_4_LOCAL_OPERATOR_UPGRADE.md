# v0.4 development: local operator provisioning and disposable-VM upgrades

> **Unreleased experimental development documentation.** These commands describe the current `main` branch, not the published v0.3.0a1 release. Use only on an isolated, disposable Ubuntu 24.04 lab VM, with a separate BIND 9 test zone and an HTTP listener bound to loopback. There is no production readiness claim.

## 1. Preserve and verify the existing VM

On the libvirt host, determine the **actual** VM address (it can change between boots):

```sh
sudo virsh list --all
sudo virsh domifaddr uddns-prealpha
sudo virsh net-dhcp-leases default
```

Check SSH and confirm the hostname before touching the guest: `ssh ubuntu@VM_IP 'hostname && hostname -I'`. Preserve a **powered-off** QCOW2 backup or reliable libvirt snapshot before changing the guest, and retain separate protected copies of `/etc/universalddns/config.json`, TSIG credentials and the SQLite state. Do not copy a live SQLite WAL database by copying only the main file. The updater includes SQLite backup handling but does **not** replace a full-VM snapshot.

For an **already installed** VM named `uddns-prealpha`, from the host:

```sh
ssh ubuntu@VM_IP 'curl -fsSL https://raw.githubusercontent.com/Monotoba/UniversalDDNSServer/main/tests/deployment/update-vm.sh -o ~/update-vm.sh'
ssh ubuntu@VM_IP 'bash ~/update-vm.sh'
ssh ubuntu@VM_IP 'bash ~/update-vm.sh --verify'
```

The updater refuses unexpected hosts and missing installations. Do not run it on a newly created but unprovisioned VM: use the [VM test-kit installation](../../tests/deployment/README.md). For an intentional DNS-writing test on the isolated zone, use `ssh ubuntu@VM_IP 'bash /opt/universalddns/src/tests/deployment/vm-test.sh update'`. The updater's rollback is best effort.

## 2. Local operator security model

The credential CLI's `issue`, `revoke` and `revoke-reference` operations call `local_operator_identity()`. It requires all of the following:

1. A **non-root** POSIX user with matching real/effective UID.
2. Membership in the host's `universalddns-operators` group.
3. Sufficient permissions to read the nonsecret configuration and write the SQLite database **and its parent directory**, including SQLite journal/WAL files. Administration does **not** require TSIG secret access.

An administrator may create the operator group and enroll a chosen human account:

```sh
sudo groupadd --system universalddns-operators  # only if it does not already exist
sudo usermod -aG universalddns-operators OPERATOR_LOGIN
```

Start a **new login session** before attempting the CLI; verify with `id -nG`. Configure narrow filesystem ACLs/groups for that operator according to the local host policy. Keep the TSIG file owned by the service account with mode `0600`; do not grant operator-group access. **Do not** use broad world-readable config permissions, change the database to mode `0666`, share the TSIG secret, or assume the service account is automatically an authorized operator. Do **not** run these commands via `sudo -u universalddns` unless that service identity is deliberately non-root and enrolled in the operator group. Since the CLI rejects UID-changing sessions, run it from a normal operator login with the appropriate direct file permissions.

The following examples assume `CONFIG` is an operator-readable path to the installed configuration and that the operator already has the required database permissions:

```sh
python -m universalddns.record_admin --config CONFIG list
python -m universalddns.record_admin --config CONFIG blockers RECORD_ID
python -m universalddns.admin --config CONFIG list
python -m universalddns.admin --config CONFIG history
```

Use the installed virtualenv interpreter (`/opt/universalddns/venv/bin/python`) if the program is not installed in the operator's active Python environment.

## 3. Record and credential lifecycle

**Create → activate → issue token → update through REST → deactivate → revoke blockers → reactivate if required.** A staged-active catalog record is visible to scoped REST clients. Staging it active never publishes DNS by itself.

Examples of local record staging (using the installed interpreter):

```sh
/opt/universalddns/venv/bin/python -m universalddns.record_admin \
  --config CONFIG create camera --name camera.lab.invalid --type A \
  --ttl 60 --address 192.0.2.40
/opt/universalddns/venv/bin/python -m universalddns.record_admin \
  --config CONFIG stage camera --revision 1 --active yes
```

The revision is an optimistic concurrency token: use the latest revision from the command response or catalog listing, not a hard-coded value after later edits. Record ID/name must not collide with static configuration. Only authorize the record **after** successful activation:

```sh
/opt/universalddns/venv/bin/python -m universalddns.admin \
  --config CONFIG issue --principal camera-client --record camera \
  --scope records:write --scope intents:read
```

**Token stdout is a bearer secret shown once**. Keep it out of shell history, logs, issue reports and shared files. Do not supply the token as a command-line argument. API publication is asynchronous; HTTP acceptance is not proof of a DNS update.

To deactivate:

```sh
/opt/universalddns/venv/bin/python -m universalddns.record_admin \
  --config CONFIG stage camera --revision CURRENT_REVISION --active no
```

Before later reactivation, inspect credentials that still grant the record:

```sh
/opt/universalddns/venv/bin/python -m universalddns.record_admin \
  --config CONFIG blockers camera
```

A nonrevoked token containing that record ID blocks reactivation. The blocker list prints references like `cred-7` but never bearer secrets or digests. A verified operator may revoke a credential using a freshly listed reference:

```sh
/opt/universalddns/venv/bin/python -m universalddns.admin \
  --config CONFIG revoke-reference --reference cred-7
```

Revocation removes **all grants** on that credential, including grants to other records. Alternatively, `admin revoke --token-stdin` accepts a bearer token through standard input. Once blockers are revoked, stage the record active at its **current** revision and issue replacement tokens. Unrevoked inactive-record grants do not authorize updates to the inactive record, and revocation cannot stop a DNS write already in flight.

## 4. Audit and verification

```sh
/opt/universalddns/venv/bin/python -m universalddns.admin \
  --config CONFIG history
```

The audit lists recent successful issuance/revocation events with a UTC SQLite timestamp, credential reference, principal and verified local operator when known. Internal library calls and legacy rows may have `operator: null`. The database audit is not tamper-evident, and it does not prove authoritative DNS publication.

After an upgrade, verify the systemd services and install checks as documented in [Deployment](DEPLOYMENT.md) and the [VM test kit](../../tests/deployment/README.md). On failure, preserve the VM snapshot and logs without token material; never retry an ambiguous DNS write without authoritative reconciliation.

## 5. Known boundaries

- Current `main` is development software; no v0.4.0a1 artifacts are asserted to be published.
- Non-root operator-group access may need explicit ACL configuration on each VM.
- Token references such as `cred-7` are SQLite row IDs, **not portable stable IDs** across database rebuild/export/reimport; refresh inventories before revoking.
- SQLite credential history does not provide tamper evidence or trusted provenance for all internal API callers.
- Catalog deactivation prevents *new* authorized submissions and worker authorization, but cannot fence an RFC 2136 write already in progress.
- The DynDNS2 compatibility route is scoped to configured static records; do not assume catalog records are exposed through that route.
- Do not expose the loopback HTTP API, plaintext Basic credentials, or TSIG keys on the public internet.

See [credential reference revocation](../features/CREDENTIAL_REFERENCE_REVOCATION.md), [controlled reactivation](../features/CONTROLLED_REACTIVATION.md), [credential operator attribution](../features/ALL_CREDENTIAL_CLI_ACTORS.md), and [credential lifecycle audit](../features/CREDENTIAL_LIFECYCLE_AUDIT.md) for implementation-specific behavior.
