# ISHTOOLS / ISHWORKZERO Distribution

## Publication policy

This directory is the public distribution record for ISHWORKZERO 0.5.0.

Before any release is promoted, the private development repository must pass its deterministic release gate. The public repository must contain only reviewed, release-safe material.

### Never publish
- credentials or access tokens
- `.env` files
- customer data
- production database files
- proof/signing private keys
- private endpoints, internal IPs or secrets
- local caches or generated runtime state

### Release verification

```text
compileall → pytest → release_gate → public sync → public CI → release verification
```

The product uses real data only. Missing configuration is `NOT_CONFIGURED`, unavailable sources are `UNAVAILABLE`, insufficient proof is `UNKNOWN`, contradictory independent evidence is `UNVERIFIED`, and independently verified success is `VERIFIED`.

## Product surface

- Core Outcome Engine
- Case Engine
- Independent Verification Engine
- Cryptographic Proof Engine
- Action Ledger
- Durable Jobs / Outbox
- Tenant isolation and RBAC
- Data Fabric and real database discovery
- Read-only Data Explorer
- Global Intelligence
- Unresolved Problems
- Company Intelligence

## Security boundary

Global intelligence is limited to lawful public/open sources and explicitly authorized customer sources. ISHWORKZERO does not perform unauthorized internet probing, exploitation, credential attacks or private discovery.

## Publication status

This directory is documentation/staging metadata. Release artifacts and binaries are published only after they have passed the release gate and public CI.
