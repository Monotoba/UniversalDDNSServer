# Project proposal

## Purpose
Develop a fully open-source, modular, self-hostable Dynamic DNS management server for homelabs, small organizations, remote gateways and educational networks. No commercial tiers, required hosted accounts or licensing enforcement.

## Problem
Existing client/server DDNS tools vary in protocol compatibility, provider support, authorization granularity, auditability and ease of operation. A compact API-first server can provide consistent update authorization and DNS publication while retaining independent backends.

## Primary users
- Homelab operators managing public and private hostnames.
- Small laboratories with geographically dispersed devices.
- Network operators using dynamic endpoints and VPN gateways.
- Developers integrating clients, routers or UDDNSUpdater.

## Goals
1. Update A and AAAA records securely and predictably.
2. Keep transports, identity/policy, orchestration, DNS backends, persistence and observability modular.
3. Expose well-documented, versioned APIs.
4. Support third-party integrations without compulsory in-process plugin loading.
5. Operate on inexpensive Linux equipment or a small VPS.
6. Maintain high test coverage and practical operator documentation.

## Out of scope for initial release
Authoritative DNS protocol implementation; remote desktop/shell; VPN tunneling; customer billing; high availability; distributed coordination; proprietary licensing.

## Success criteria
A fresh installation can configure RFC 2136/TSIG, enroll a restricted client, update an A/AAAA record over HTTPS, read an audit entry and pass automated integration tests against an isolated authoritative DNS server. Invalid/unauthorized requests must not alter DNS.
