# ADR-0003: Bounded isolated acknowledgement framing

PR #118 replaces Python object serialization on the parent-created child
acknowledgement pipe with a fixed 52-byte binary body: four-byte magic
`UACK`, 32-byte invocation nonce, and 16-byte UUID generation. The
multiprocessing Connection's existing transport-level length prefix is
consumed through `recv_bytes(52)`, which refuses oversized messages rather
than allocating and unpickling arbitrary Python objects.

Validation rejects undersized, oversized, corrupt, incorrectly challenged,
and wrong-type bodies. A second queued message is rejected; ordinary EOF
after the child's clean exit remains acceptable. The sender writes only via
`send_bytes`. Parent still requires successful child exit and matching
independent snapshot read before volatile registry issuance.

This is an **isolated** child protocol and neither network framing nor a
general authenticated IPC design. A compromised authorized child knows the
challenge and can construct the byte frame. The parent-controlled launch,
directory permissions, exclusive-writer constraints, crash semantics, and
consumer trust boundaries still require review before deployment.

No broker, VM, systemd, accounts, ACLs, live database, DNS or release changes.
