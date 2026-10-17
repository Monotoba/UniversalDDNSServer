# ADR-0003: Isolated filesystem publisher-authorization boundary

PR #116 supplies two complementary negative acceptance fixtures.

1. A direct producer in a separate process deliberately ignores the observer
   session lock and still publishes a replacement while that lock is held.
   The test records the changed generation and proves that an unissued registry
   must reject its bytes. Cooperative flock is not mandatory access control.
2. In a root-provisioned disposable Linux fixture, a producer-owned private
   directory is restricted to UID 65533 (mode 0700), with its source database
   mode 0600. A child using UID 65534 cannot open the restricted path for
   replacement, publish through the standard producer, or acquire a spoofed
   observer session. The approved producer performs a real publication first,
   and the snapshot generation is unchanged after unauthorized attempts.

The privileged CI fixture does not create users, update persistent ownership
or ACLs, or alter production directories. Such filesystem denial rests on
kernel discretionary access controls, private ancestor directories, separate
UIDs, and the absence of extra privileges or pre-opened writable descriptors.
Root, capable processes, same-UID untrusted code and shared writable
directory access are outside the demonstrated boundary.

The checks do **not** implement an authenticated acknowledgement protocol,
a production privilege-drop service, or durable issuance across restart.
An attacker controlling an authorized publisher or its acknowledgement
channel remains outside these guarantees. Next work should test delegated
publisher capability construction and descriptor/IPC provenance without
changing the production broker or service wiring.
