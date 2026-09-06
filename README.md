# ISHWORKZERO

**AI Outcome Assurance / Proof Infrastructure**

ISHWORKZERO independently verifies whether an intended real-world outcome actually occurred. An agent's `done` claim is never treated as proof.

## Core lifecycle

`PLAN → EXECUTE → VERIFY → PROVE → CLOSE`

Core capabilities include outcome contracts, independent verification, cryptographic proof, Action Ledger, durable jobs/outbox, tenant isolation, RBAC, real-data Data Fabric, read-only Data Explorer, Global Intelligence and Unresolved Problems.

## Real-data policy

No mock or fabricated operational data. Missing configuration is `NOT_CONFIGURED`; unavailable sources are `UNAVAILABLE`; insufficient proof is `UNKNOWN`; contradictory independent evidence is `UNVERIFIED`; independently verified success is `VERIFIED`.

Global intelligence uses lawful public/open sources and explicitly authorized customer sources. The platform does not perform unauthorized probing, exploitation, credential attacks or private discovery.

## Distribution

This repository is the public ISHTOOLS distribution surface. Release artifacts must pass the release gate before publication. Never publish credentials, `.env` files, database files, proof keys, private endpoints or customer data.

See `distribution/ISHTOOLS/ISHWORKZERO/README.md` for the release/publication policy.

## Verification

```bash
python -m pip install -e '.[test]'
python release_gate.py
```

Docker support is provided by the included `Dockerfile`.
