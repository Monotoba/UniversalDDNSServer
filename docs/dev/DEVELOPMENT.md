# Development guide

The repository is currently a design baseline; no server build or runtime command exists.

## Workflow
- Propose interface changes via GitHub issue and ADR.
- Work in focused branches and preserve existing behavior when refactoring.
- Develop by module, with mock ports and independent conformance suites.
- Add regression, authorization-negative and failure-recovery tests to each change.
- Run formatting, static checks, unit, integration and documentation validation tests.
- Update README, implementation plan and CHANGELOG before merge.
- Commit locally using descriptive messages; open a PR and wait for CI.

## Initial layout (planned)
```text
src/universalddns/{api,auth,domain,orchestration,ports,adapters,events}
tests/{unit,integration,contracts,security}
docs/{architecture,dev,operations,standards}
```

Runtime language/framework selection is deferred to its own ADR to avoid premature constraints.
