# Testing

Two suites, deliberately separate.

| | What it does | Needs credentials | Needs network |
| --- | --- | --- | --- |
| **Unit** (`tests/*.py`) | Mocks the HTTP layer with `responses` and exercises the SDK's own logic | No | No |
| **Integration** (`tests/integration/`) | Calls a real inmydata platform through the SDK | Yes | Yes |

The integration tests are **skipped unless you pass `--integration`**, so a plain
`pytest` run stays offline and needs no setup.

## Setup

From the repository root, in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

`-e` installs the package in editable mode, so your edits to `src/inmydata/` take effect
without reinstalling.

Then, for the integration tests only:

```powershell
Copy-Item .env.example .env
```

and fill in `.env`. It is gitignored — do not commit it, and do not paste API keys into
issues or pull requests.

## Running the unit tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

76 tests, well under a second, no network. This is what runs in CI on a release tag.

## Running the integration tests

Start with connectivity. It fails with a specific message for each of the three things
that usually go wrong, rather than a generic timeout:

```powershell
.\.venv\Scripts\python.exe -m pytest --integration -v -s tests/integration/test_connectivity.py
```

`-s` matters: the suite prints which host it is talking to, and the schema test prints
every API-enabled subject for your key. That listing is how you fill in
`INMYDATA_TEST_SUBJECT`.

Then the rest:

```powershell
.\.venv\Scripts\python.exe -m pytest --integration -v -s tests/integration
```

Everything is read-only except `get_chart`, which registers a visualisation on the
platform. That one also needs an explicit opt-in:

```powershell
.\.venv\Scripts\python.exe -m pytest --integration --include-write-tests -v -s tests/integration
```

### Choosing the environment

`INMYDATA_ENV` picks a profile, `test` or `live`, and each has its own base URL and API
key so the two never share a variable. It **defaults to `test`**, so forgetting to set it
cannot aim a run at production.

To run against live for one command, without editing `.env`:

```powershell
$env:INMYDATA_ENV = "live"
.\.venv\Scripts\python.exe -m pytest --integration -v -s tests/integration
Remove-Item Env:\INMYDATA_ENV
```

If a profile's URL or key is missing, its tests **skip with a message naming the variable**
rather than failing.

## In VS Code

`.vscode/settings.json` and `.vscode/launch.json` are committed, so this works out of the
box once `.venv` and `.env` exist:

- **Test Explorer** (the beaker icon) discovers and runs the unit tests. The integration
  tests appear but skip, because the Test Explorer does not pass `--integration`.
- **Run and Debug** (the play icon) has four configurations: unit tests, integration
  connectivity only, all read-only integration tests, and the same against live. These
  load `.env` and pass the flags, and you can set breakpoints in `src/inmydata/`.

If the interpreter is not picked up, run **Python: Select Interpreter** and choose
`.venv\Scripts\python.exe`.

## The base URL, and why the SDK does not take one

This is the part worth understanding before you debug a connection problem.

**The SDK has no base URL parameter.** Every driver builds its URLs like this:

```python
url = 'https://' + self.tenant + '.' + self.server + '/api/developer/v1/ai/data'
```

So the host is always `{tenant}.{server}`, assembled from two constructor arguments.

The integration harness therefore takes the base URL you configure, splits its host at the
first dot, and passes the halves as `tenant` and `server`. For
`https://api.test-inmydata.com` that gives `tenant="api"`, `server="test-inmydata.com"`,
which reassembles to exactly the host you asked for. The `tenant` half is a routing
artefact here rather than a real tenant name, and that is fine: the platform reads the
actual tenant from the `imd_tenant` claim on the API key, not from the hostname
(`GetTenant()` in the web application's controllers).

Consequences:

- A host with no dot, a port, or a path cannot be expressed. The harness rejects these
  with an explanatory error instead of building a broken URL.
- If splitting at the first dot is wrong for some host, set `INMYDATA_<ENV>_TENANT` and
  `INMYDATA_<ENV>_SERVER` directly; they override the base URL.

### Known state of the two hosts

Checked on 1 September 2026:

- **`api.test-inmydata.com`** resolves to the test web application load balancer, and an
  unauthenticated POST to `/api/developer/v1/ai/getapisubjectlistinfo` returns **401 with
  an empty body**. That is the web application refusing the request, so the route is
  served there. This host is correct for the test system.
- **`api.inmydata.com`** resolves to an AWS API Gateway
  (`execute-api.eu-west-1.amazonaws.com`), and the same request returns **403
  `{"message":"Missing Authentication Token"}`** — API Gateway's stock reply, not the web
  application's. Sending a Bearer token to it is refused with `Invalid key=value pair
  (missing equal-sign) in Authorization header (hashed with SHA-256 and encoded with
  Base64)`, which is AWS SigV4 complaining: that host expects signed AWS requests, not
  the Bearer token the SDK sends. It is a different service, and `api.inmydata.com`
  appears nowhere in the platform source. In production the developer API is served per
  tenant, so `INMYDATA_LIVE_BASE_URL` is normally `https://<yourtenant>.inmydata.com`.

`test_endpoint_exists_and_requires_authentication` in `test_connectivity.py` encodes both
checks, so if any of this changes the test tells you rather than the docs going stale.

## What the integration tests actually prove

Beyond "the network works", they check the behaviour 0.0.19 introduced, against real
responses rather than mocks:

- An invalid API key **raises** `InmydataAuthenticationError` or
  `InmydataAccessDeniedError` with a `status_code`, instead of returning `None`.
- A filter matching no rows returns an **empty DataFrame with the requested columns**,
  not `None` — the distinction that stops a silent auth failure looking like an empty
  result.
- Requested fields come back as columns **in request order**.
- `caseSensitive=False` matches at least as many rows as `caseSensitive=True`, which is
  the inversion 0.0.19 fixed.
- `get_chart` works with `TopNUsed` omitted, which used to raise `AttributeError`.
- The calendar's genuine not-found cases still return `None` rather than raising.

## Adding tests

Unit tests go in `tests/`, use `responses` to mock HTTP, and must not touch the network.
Integration tests go in `tests/integration/`, must carry
`pytestmark = pytest.mark.integration`, and should `pytest.skip` with a clear reason when
the platform is not configured for what they need rather than failing.

Anything that creates or changes data on the platform must be gated behind
`--include-write-tests`, as the `get_chart` test is.
