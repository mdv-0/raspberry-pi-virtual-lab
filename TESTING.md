# Testing

Install development dependencies with `.venv/bin/pip install -r requirements-dev.txt`. Provision the guest, expose `qemu-system-aarch64` and `qemu-img` on PATH, then run:

```bash
./scripts/test.sh
```

`test_real_guest_full_lifecycle` runs actual ARM64 QEMU with its own temporary SQLite database, qcow2 disk, UART PTY, Unix sockets and SSH port 2234. No guest commands or emulator responses are mocked. It checks:

- Linux boot messages, login prompt and successful AArch64 SSH command.
- Real host-side pyserial PTY login, transmitted command and guest response.
- File writes, graceful shutdown, reboot and persistent data.
- Actual carrier 0 reported over UART after QMP disconnect, SSH failure, carrier 1 and SSH recovery after reconnection.
- Rejection of live boot-media ejection, hardware reset, forced shutdown, process reaping and PTY removal.

The API test checks real PTY endpoint lifecycle, cross-origin/Host denial, invalid media imports and state validation. Real guest testing is explicitly skipped if QEMU or provisioned assets are missing; a skipped test is not boot verification. Setup prepares SSH in advance. Guest tests allow 180 seconds for boot and roughly one minute for lifecycle operations. Tests require no privileged operations or host network changes.

Browser integration:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

By default Playwright starts and cleans up a disposable server on port 8001, a private runtime and SSH port 2240. It refuses to reuse an existing server, preserving the student's running instance. Screenshots and traces are written to ignored `frontend/test-results/`.

The test creates/inserts a real disk through the UI, connects UART and verifies a character-device endpoint, and powers on actual QEMU. It waits for SSH to confirm a fresh ARM64 guest is ready, then launches an external Python serial client to log in and verify a real guest command response through the host PTY. It checks that the page creates no WebSocket connections, mounts no terminal/canvas, offers no browser console/viewer buttons, and rejects browser UART mode. It also checks Ethernet controls, graceful shutdown, and responsive layout. There is no guest or command simulation.

The suite can target `RPI_LAB_TEST_URL=http://127.0.0.1:8001 npm run test:e2e`. It reads the SSH forwarding port from backend status. Use a separate runtime, SSH port and allowed Origin for that test server to avoid disturbing a student's running board.

Static validation: `cd frontend && npm run build`. `npm audit` reports dependency advisories. Browser terminal/noVNC dependencies have been removed. API tests check that both legacy console WebSocket endpoints close with policy code 1008 and that UART browser mode is rejected even for a trusted local client.

Launcher regression tests start an actual HTTP server and verify instance reuse, lock-owner metadata, stale lock handling, and concise busy-runtime errors. The live-server test skips while port 8000 is occupied; other tests run independently. Optional host tools are picocom for manual UART and libguestfs for offline image editing. No automated test needs root, TAP or host network changes.


Imported-image regression tests validate raw ext4, MBR and GPT, reject truncated partitions/checksum errors, check path/upload imports, copied kernel artifacts, database persistence and reset-to-import behavior. The partitioned-image integration test builds a real MBR disk from the Alpine rootfs, supplies a matching custom initramfs/kernel, boots it in QEMU, verifies a persistent guest write across reboot, then verifies Reset removes the write.

Optional official Pi OS boot verification (decompress the image first):

```bash
RPI_LAB_TEST_PI_IMAGE=/absolute/path/to/2023-12-05-raspios-bullseye-arm64-lite.img ./scripts/test.sh tests/test_integration.py::test_official_pi_image_boot
```

This boots an actual raspi3b SD image and waits for UART login/user setup, using a private runtime and SSH port 2237. It does not inject credentials or validate desktop/network functionality. Image download is not part of the test suite.
