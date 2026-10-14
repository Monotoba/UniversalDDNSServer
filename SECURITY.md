# Security policy

**Status:** experimental pre-alpha; no supported production deployment or security certification exists. A private Ubuntu VM installation has been validated, not an internet-facing server.

Do not publish vulnerabilities, credentials or exploit proofs in public issues. Contact the maintainer privately through GitHub's private vulnerability reporting when enabled, or a privately agreed secure channel. No response-time SLA is promised.

Planned security controls: TLS; per-record scoped credentials; constant-time secret comparisons where relevant; encrypted secret handling; request limits; replay/race protections; strict zone/hostname/IP validation; audit trail; least-privilege DNS update credentials; secure-by-default network bindings; and third-party plugin isolation recommendations.

Never load unknown plugins into a privileged process. Do not assume a DNS update creates network reachability behind CGNAT or firewalls.
