# ADR-0003: Real Linux SCM_RIGHTS truncation acceptance

PR #160 exercises the actual Linux AF_UNIX datagram sendmsg/recvmsg path.
Disposable tests inject 16 SCM_RIGHTS descriptors against the receiver's
four-descriptor ancillary buffer to exercise MSG_CTRUNC, and test smaller
multi-descriptor messages, malformed payloads and payload truncation.
They compare the open descriptors targeting the fixture file before/after
rejection, while retaining a known-good reference FD.

The observed MSG_CTRUNC flag is asserted in a separate real-recvmsg test.
The tests are Linux-specific and do not claim portability across Unix
kernels. They do not change runtime socket handling or production services.
