# ADR-0003: Acknowledgement partial-frame deadline and recovery

PR #119 hardens the isolated parent-created-child acknowledgement transport
against a peer which sends a valid length prefix but stalls partway through
the fixed-size payload. Instead of relying on `Connection.poll` followed by
a potentially unbounded `recv_bytes`, it reads the transport's four-byte
big-endian length and exactly 52 payload bytes using `select` and bounded
`os.read` operations against one monotonic deadline. Unexpected frame lengths,
EOF, partial data, and timeouts fail closed. Following clean child exit, any
trailing byte is rejected as an extra message; EOF is accepted. Failure
cleanup terminates/reaps the publisher, closes owned endpoints, and invalidates
volatile issuance. Tests exercise truncation, oversize length, stall,
duplicate, and subsequent successful recovery.

This is still the existing isolated POSIX fork-and-Pipe fixture, not a
publicly exposed wire protocol or independent sender-authentication channel.
The parent must control child creation and the sole-writer filesystem boundary
before production integration. A child compromised with access to the private
channel may still send syntactically valid frames. No VM, service, broker,
ACL, live database, DNS, or release changes.
