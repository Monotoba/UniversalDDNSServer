# Deployment requirements (future)

No deployable server exists yet.

Recommended topology: HTTPS reverse proxy -> least-privileged UniversalDDNSServer process -> local SQLite and authenticated authoritative DNS backend. Use a stable VPS or stable DNS infrastructure for authoritative zones; hosting authoritative servers solely behind a changing residential IP is not a reliable public DNS design.

Requirements: DNS credentials restricted to intended zones/records; TLS; backups of state/config/key material; monitored storage; log retention; restart policies; health checks; tested restoration; host firewall configuration.

Do not confuse DNS address mapping with NAT traversal. CGNAT, firewall rules and unavailable public IPv6 can prevent incoming connectivity even when records update successfully.
