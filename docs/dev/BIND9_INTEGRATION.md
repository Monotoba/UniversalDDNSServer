# BIND 9 DNS integration

The GitHub Integration tests workflow installs BIND 9 and runs
`tests/integration/test_bind9.py` against an ephemeral authoritative server
bound to loopback on a dynamically allocated unprivileged port.

Each test run creates a disposable `example.test` zone and a dummy TSIG key.
It verifies that RFC 2136 updates actually modify A and AAAA RRsets, that
replacement semantics work, that bad TSIG credentials do not update records,
and that cross-zone writes are rejected by the adapter.

Run on an Ubuntu system with `named` installed:

```sh
python -m pip install -e .
python -m unittest discover -s tests/integration -p 'test_*.py' -v
```

If BIND is not installed, the BIND test class is skipped; the dedicated
GitHub workflow installs BIND so the checks execute rather than skip.

This tests only a local authoritative DNS instance. It does not establish
external DNS propagation or globally reachable services.
