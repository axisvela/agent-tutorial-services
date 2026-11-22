# Agent Tutorial Services

Shared synthetic business services for native agent tutorials. MIT-licensed,
locally runnable, with no model credentials or third-party Python dependencies.
This repository provides business APIs, not an agent loop or a product platform.

The first service supports order review. It is used by the Python, TypeScript,
Java and C# [PRAXO-CORE tutorials](https://github.com/axisvela/praxo-core/tree/main/language).
Clients keep their native Core, tool registry, policy and model adapters. Other
frameworks can use the same HTTP API without installing Core in this service.

## Start Locally

Requires Python 3.12 or newer:

```bash
git clone https://github.com/axisvela/agent-tutorial-services.git
cd agent-tutorial-services
python service/orders.py
```

The server binds only to `127.0.0.1:8765`. Use `--port` for a different port.
There is no public hosted endpoint. Public source availability is not evidence
of production deployment, security certification or independent adoption.

## Order API

See [OpenAPI contract](contracts/orders-v1.yaml).

| Operation | Route | Result |
| --- | --- | --- |
| Health | `GET /healthz` | Status and fixture version |
| Read order | `GET /v1/orders/{order_id}` | Synthetic order and shipment status |
| Create draft | `POST /v1/orders/{order_id}/drafts` | A resolution draft, not an order mutation |

The public fixture token `demo-a-token` can access `order-100`; `demo-b-token`
can access `order-200`. These tokens are example constants, not secrets or
production authentication. Do not use real personal, banking or customer data.

From another terminal:

```bash
curl http://127.0.0.1:8765/v1/orders/order-100 -H "Authorization: Bearer demo-a-token"
curl -X POST http://127.0.0.1:8765/v1/orders/order-100/drafts -H "Authorization: Bearer demo-a-token" -H "Content-Type: application/json" -H "Idempotency-Key: review-1" --data '{"recommendation":"Contact carrier"}'
```

On Windows PowerShell use `curl.exe`, or invoke the Python/Java/TypeScript
tutorial clients instead of shell-specific JSON quoting.

The draft's status is `draft_only`. Repeating the same tenant/order/key and
recommendation returns the original draft. Reusing the key with a different
recommendation returns 409. Cross-tenant calls return 403 before creating drafts.
The service never refunds, transfers money, changes orders or controls devices.

## Tests

```bash
python -m unittest discover -s tests -p test_orders.py -v
```

The tests use disposable in-memory state and ephemeral loopback ports. They
cover tenant denial, authentication, draft replay/conflict, invalid input and
dependency failure. The service's own CI runs these tests without Core.

To test the native Core clients, install their pinned dependencies first:

```bash
python -m pip install -r ../praxo-core/language/python/Tutorial/order-review/requirements.txt
npm ci --prefix ../praxo-core/language/typescript/Tutorial/order-review
```

Set `PRAXO_CORE_REPO` to the absolute Core checkout path, then run:

```bash
python -m unittest discover -s tests -v
```

Python client tests default to Core source mode. Set
`PRAXO_PYTHON_PACKAGE_PATH` to an isolated package installation to verify a
published package instead. TypeScript resolves the installed tutorial package.
Java client integration is opt-in: build its tutorial and set
`PRAXO_JAVA_CLASSPATH` to its compiled classes plus runtime dependency jars.
The `JAVA` variable optionally selects a launcher executable.

For C#, build `language/csharp/Tutorial/order-review/OrderReview.csproj` and set
`PRAXO_DOTNET_DLL` to the absolute compiled `Praxo.OrderReview.dll` path.
`DOTNET` optionally selects the .NET launcher. This enables both C# CLI checks
and a real ASP.NET Core Web entry against the local business service. The Web
test covers missing-credential denial, successful draft creation, replay and
dependency failure, and terminates its child process even on failure.

Without `PRAXO_CORE_REPO`, native-client integration is skipped, not passed.
Each enabled client is checked for success, Agent policy denial, independent
server denial and dependency failure. Core's tutorial CI pins this backend to
an immutable commit so neither repository needs to execute an unreviewed `main`.

## Recorded Verification

On 2026-11-22, standalone backend tests passed in
[CI run 45032761254](https://github.com/axisvela/agent-tutorial-services/actions/runs/45032761254)
at service revision `8b7820e`.

Core [CI run 45033109188](https://github.com/axisvela/praxo-core/actions/runs/45033109188)
at Core `8b0593bb` pinned that service revision and passed all four unittest
methods, including Python, TypeScript and Java native CLI clients against a real
ephemeral loopback service. Each client exercised successful draft creation,
Agent policy denial, independent server denial and unavailable draft storage.
Clients used published PyPI `0.10.0`, npm `0.9.0` and Maven Central `0.11.0`.
Java mock/Web JUnit passed separately. These are deterministic maintainer-run
checks, not a live model, public endpoint, production deployment, or independent
consumer. Source and API availability should not be confused with those claims.

C# follow-up: Core `ae953050` pinned backend `cd08b09` in
[run 45034303513](https://github.com/axisvela/praxo-core/actions/runs/45034303513).
All five unittest methods passed, including four native CLI clients and the
C# ASP.NET Core Web entry against a real backend. C# used NuGet `0.10.0` and
.NET 8; its standalone scripted-transport/Web self-tests also passed separately.
The Web path verifies authentication denial, successful draft, idempotent replay
and store failure. This is deterministic loopback evidence, not production
identity, a live model or public hosting.

## Boundaries

- In-memory drafts disappear on restart; this is not a database or durable ledger.
- Fixture keys and process-local locking do not establish exactly-once effects.
- No rate limiting, production identity, retention, deployment or public-hosting
  guarantees are supplied. Do not expose this teaching HTTP server to the internet.
- No order, HR, bank or device domain is promoted to a Core compatibility contract.
- Future domains follow runnable consumer paths, not a feature-count target.

## Provenance

The initial order service, contract and tests were extracted from AxisVela's
maintainer-owned shared teaching slice on 2026-11-22, with explicit approval to
publish this subset. No other demo content, private datasets, credentials or
repository history is included. Future teaching-service changes belong here;
the earlier private snapshot is not a second maintained implementation.

See [LICENSE](LICENSE). This repository does not depend on AGPL product code.
