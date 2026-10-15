# Staged record activation — v0.4 development

Persisted catalog records now carry an `active` flag, defaulting to false during both new creation and migration of preexisting catalog entries. The local authorized operator CLI can stage a record for eventual activation:

```sh
python -m universalddns.record_admin --config /etc/universalddns/config.json stage lab --revision 1 --active yes
python -m universalddns.record_admin --config /etc/universalddns/config.json stage lab --revision 2 --active no
```

Each change requires the current revision and increments it atomically. Conflicts with static configuration are rejected. A caller without the designated local operator authorization cannot use this command.

**Safety boundary:** staging does **not** activate runtime routing. The API and DNS publication worker continue using config.json; staged entries cannot yet be discovered or published by clients. Before connecting the catalog to live runtime, implement dynamic token scope validation, consistent server/worker snapshots, collision checks at request time, and activation tests against isolated BIND 9. This staged flag is preparatory metadata rather than a production activation switch.
