# Contributing

Keep hardware claims tied to QEMU devices and real integration evidence. Extend the profile registry and driver capabilities before enabling connector UI. Never add a fake shell or fake boot output. Run `./scripts/test.sh`, `cd frontend && npm run build`, and the Playwright suite for UI changes. Use unprivileged execution, typed Python/TypeScript boundaries and parameterized SQLite. Record new hardware constraints in HARDWARE_SUPPORT.md.

Guest artifacts are downloaded locally and excluded from Git. Preserve upstream licensing and source pointers when redistributing binaries. Alpine includes individually licensed packages, Linux is GPL-2.0-only, and QEMU has its own licensing; the repository's MIT license does not relicense them.


Formatting and static checks:

```bash
.venv/bin/ruff check backend emulator scripts tests
.venv/bin/ruff format --check backend emulator scripts tests
cd frontend
npm run format:check
npm run build
```

`npm run test:e2e` starts a disposable test server on port 8001 with its own runtime and SSH port 2240. It refuses to reuse an occupied port. Never point browser lifecycle tests at a student's active instance. An explicit `RPI_LAB_TEST_URL` opts into an independently prepared test server.
