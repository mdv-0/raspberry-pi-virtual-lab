# Validation — 2026-10-23

Host: Ubuntu x86_64, Python 3.12, QEMU 9.0.2 with ARM64 TCG. Tests use private runtimes and separate SSH ports. The student's running guest is preserved.

## Automated checks

- Ruff lint and formatting checks for backend, emulator, scripts and tests.
- TypeScript / Vite production build and Prettier formatting check.
- Python dependency consistency and exact installed/lockfile version comparison.
- npm audit: zero reported vulnerabilities at review time.
- Shell syntax validation for launcher, setup and test scripts.
- Full backend run including optional Pi boot: **15 passed, 1 skipped**; the launcher test skipped because the student's server occupied port 8000. A subsequently added GPT metadata-overlap regression passed in the storage suite (**10 passed**).

## Actual guest verification

- Bundled Alpine ARM64: UART login through the host PTY, guest command execution, DHCP/SSH, QMP Ethernet carrier changes, shutdown/reset, persistent rootfs writes and process cleanup.
- MBR-partitioned Alpine rootfs with explicitly supplied kernel/initramfs: boot from `/dev/vda1`, persistent write across restart, reset to the imported baseline.
- Official **2023-12-05 Raspberry Pi OS Lite Bullseye ARM64**: `raspi3b` machine, FAT boot artifact extraction, emulated SD/MMC, serial login/user-setup prompt. Desktop and full peripheral support are not inferred from successful boot.

## Browser verification

Playwright uses a disposable server by default. The real-guest test verifies power/network controls, a real external pyserial login/command, graceful shutdown, no browser terminal/canvas/WebSocket console, and desktop/mobile layout. A second test covers theme persistence, eject-before-delete, cancel/confirm deletion and empty-boot-media navigation. Screenshots and failure traces are generated in ignored `frontend/test-results/`, not checked into source control.

Run instructions: [TESTING.md](../TESTING.md). Review scope and remaining limitations: [REVIEW.md](REVIEW.md).
