# Web Demo V1 — local acceptance

Implementation evidence for Architect review. No merge, public deployment or
live provider execution is included in this acceptance.

## Contract and baseline

- Contract SHA256: `5f107bfed6ee1eb3ac060bac7a7b9ba79afb13397d45d9bd38a62b430c9fabf0`
- Contract size: 19,345 bytes / 1,016 lines; read in full before implementation.
- Workspace was empty before cloning the existing repository.
- Base commit: `9c23c6b74dbd5328f84008a25a42a8126efc0c64`
- Base tree: `7011cd946906dadef70961e00518cfbf2c3e136a`
- Origin: `luh0pump/ai-company-evaluation-pipeline`
- Target branch: `feat/web-demo-v1`; absent locally and remotely before creation.
- Python: 3.12.14 in a repository-local virtual environment. System Python 3.9.6
  was not used because the repository requires 3.11 or newer.
- Installed the unmodified development package first: 7 baseline tests passed,
  and baseline source compilation passed.

## Local acceptance results

| Gate | Result |
| --- | --- |
| Full test suite | 32 passed; no failures |
| Compile all source | PASS |
| Dependency consistency | PASS (`pip check`) |
| Staged and working diff whitespace | PASS |
| Tracked files and staged diff secret scan | PASS; only empty environment placeholders and a removed documentation placeholder matched |
| HTTP health / root / demo run | 200 / 200 / 200 |
| Demo rows | 8 |
| Successful rows | 7 |
| Controlled failures | 1, existing `CACHE_MISS` status |
| Average score | 53.7, independently calculated from the 7 successful rows |
| Cache rate | 87.5%, independently calculated as 7 / 8 |
| Runtime | Positive measured server duration; varies per run |
| CSV / JSON | Actual browser downloads matched the current API exports byte-for-byte |
| Public fetch / OpenAI / Anthropic | Forbidden constructor and method spies remained untouched; invalid overrides rejected |
| Invalid provider output | Rejected as `EVALUATION_ERROR`; no successful score assigned |
| Error handling / template escaping | Controlled response, no raw exception, escaped prompt markup |
| Package installation | Built wheel includes all 5 web assets; installed-wheel root, health, static routes and 8/7/1 run pass from an unrelated working directory |
| Browser | Layout and all 8 rows inspected at 1440 × 900; controlled failure visible in the first viewport |
| Interactive controls | Run, rerun, success details, failure details, close, reset and both exports checked |
| Browser console | No warning or error entries during acceptance |
| Local server | Bound only to 127.0.0.1; stopped after acceptance, port closure verified |
| Final diff | Manually reviewed, including core changes, UI, configuration, tests and documentation |

The downloaded synthetic CSV was 2,188 bytes with SHA256
`22448be2976114dbe99c3f423127cb49bdc6704c78f4a6de53cf1847fa009878`.
The JSON was 3,864 bytes with SHA256
`2354e2f64570e18f10ae16c73fe91ac407a04febf05d84f6172bf094940aee32`.
Runtime is summary metadata and is not included in these row exports.

Local acceptance start command:

```bash
APP_MODE=portfolio ALLOW_LIVE_FETCH=false ALLOW_LIVE_PROVIDERS=false \
  .venv/bin/company-eval web --host 127.0.0.1 --port 8765
```

Acceptance URL: `http://127.0.0.1:8765` (server stopped).

## Boundaries and remaining review

The web interface remains a fixed offline demo in both application modes.
Local/self-hosted live input, prompts and providers use the explicitly enabled
CLI. No upload endpoint was added. No live SDK calls or website requests were
used for acceptance, and tests deny network sockets and remove inherited keys.

CI installs development and web extras and runs the suite plus compilation.
Render configuration uses a free Python service, the health route, explicit
portfolio flags, no secrets or persistent disk, and `autoDeployTrigger: off`.
It has not been deployed or validated against a running Render service.

Two nonblocking warnings originate in the installed Starlette test client:
its httpx integration and its AnyIO BlockingPortal alias are deprecated. They
do not affect the passing tests or observed application behavior.

Architect code and visual acceptance remain required. No screenshot was added
to the repository. The final commit/tree and remote branch receipt are provided
separately after the feature-branch push.
