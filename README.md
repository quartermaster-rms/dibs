# dibs

QUARTERMASTER's equipment service: reserve equipment on a shared calendar,
energize tools through hardware interlocks, file issue reports that drive a
red/yellow/green health status, and enforce dual reserve/usage quotas. Identity
comes from Keycloak; dibs owns its fine-grained equipment permissions.

## Run it

The whole system is one Docker Compose deployment. You need Docker Engine + the
Compose plugin and a `deploy/host.env`:

```sh
cp deploy/host.env.example deploy/host.env   # then edit it
bash deploy/gen-dev-tls.sh                   # self-signed device-port cert (dev)
make deploy                                  # build + start (bounded auto-recovery)
```

The api is published on `127.0.0.1:${API_PORT}` — put a TLS-terminating reverse
proxy in front of it. The interlock device port `${DEVICE_PORT}` terminates its
own TLS (nodes pin the CA). Postgres and Redis stay on the internal network.

Open the app at the api URL. In the dev profile (`AUTH_MODE=stub`) sign in with
any username plus comma-separated groups — `admin-dibs` for the admin surface,
`group-*` for departments. Production sets `AUTH_MODE=oidc` (Keycloak SSO).

## Develop

```sh
make install     # virtualenv + backend deps + frontend deps
make test        # the full gate: backend + frontend (spins up isolated pg/redis)
make lint
```

`make test` is the single gate; GitHub Actions just runs it. `make test-deploy`
builds and verifies the production image end to end.

## Configuration

`deploy/host.env` is the only file needed to start the stack — connections,
timezone, identity, and TLS. Everything else — quotas, limits, the permission
model, the reservation slot granularity, the department gate — is configured
in-app by admins on the Settings page.

## Layout

- `src/dibs/` — FastAPI backend: user api, interlock device plane, worker,
  scheduler.
- `frontend/` — React + TypeScript SPA, served by the api.
- `deploy/` — Dockerfile, Compose stack, `host.env` template.
- `SPEC.md` — the service specification.
