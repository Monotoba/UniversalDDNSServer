# Local operator authorization for recovery proposals

Recovery proposal recording requires a non-root POSIX account whose real and effective UIDs match and whose account belongs to the dedicated `universalddns-operators` group. Authorization fails closed when the group is missing. The CLI does not accept a caller-supplied operator identity.

For an isolated Ubuntu development VM, an administrator may provision the group and grant a specific account membership:

```sh
sudo groupadd --system universalddns-operators
sudo usermod -aG universalddns-operators OPERATOR_ACCOUNT
id OPERATOR_ACCOUNT
```

Replace `OPERATOR_ACCOUNT` with the existing intended local account. A new login session is required for newly granted membership to take effect. The operator must separately have narrowly scoped filesystem access to the SQLite database and its parent directory for writing; group membership itself does not grant database access. Do not make the database world-writable or grant arbitrary users write access. Database credentials and DNS secrets must remain protected.

**Security limits:** this authorization only gates the local `propose` command. Group membership and the proposal journal do not authorize DNS updates, intent-state transitions, or force-unblocking. Compromise of an authorized OS account or host administrator privileges can still undermine local evidence. This is experimental development guidance, not an approved production deployment procedure.
