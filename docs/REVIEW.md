# Review — 2026-10-23

Reviewed backend lifecycle and storage, QMP/UART boundaries, frontend flows, setup scripts, dependency manifests and test isolation. Fixed issues are covered by regression checks.

| Finding | Resolution |
|---|---|
| Polling status during disk creation could encounter a `pending` filename before the image existed | Build the image first, then publish its complete database row. Regression test polls while creation is suspended. |
| Replacing kernels/initramfs/DTBs retained unused copies | Reclaim only unreferenced files within private storage after a successful save. Failed saves retain the previous configuration. |
| Cancelling image conversion could leave a child process | Kill and reap `qemu-img` before unwinding a cancelled operation. |
| GPT checksums alone allowed partitions overlapping GPT metadata | Validate header geometry and the usable LBA range; test a checksum-valid but invalid partition. |
| Status polling read the entire emulator log | Seek to and read only the final 8 KiB. |
| Finished lifecycle tasks accumulated on repeated starts | Prune completed tasks before adding a new guest lifecycle. |
| Browser tests could target the student's instance by default | Start a disposable server/runtime on port 8001 and separate SSH port; refuse server reuse. |
| Stale console screenshots, historical validation claims and obsolete CSS | Remove old screenshots/debug artifacts, replace validation notes and delete unused styles. |
| Python lockfile differed from the declared/installed WebSocket dependency | Align the lockfile with the installed compatible version and add a reproducible lint tool/config. |

Removed about 665 MiB of generated development files: staging root filesystems/modules, obsolete QEMU package downloads, debugging scripts/screenshots, caches and a redundant compressed Pi image. Preserved the decompressed Pi test image, downloaded boot assets, runtime/student media, local management keys, and the QEMU binaries used by the running guest. Generated assets and secrets are ignored by Git.

Validation includes static checks, unit/API/storage tests, actual QEMU virt lifecycle, a partitioned custom-kernel boot with persistent writes/reset, official Pi OS Lite 64-bit UART boot, and Playwright tests using the real guest. See [VALIDATION.md](VALIDATION.md).

Limits: a fresh Ubuntu installation and complete Alpine re-provisioning were not repeated. Kernel/package downloads remain rolling within the Alpine release branch; preserve local assets and manifest for exact reproduction. Upstream FastAPI/httpx and pyfatfs/fs emit deprecation warnings. Pi desktop/peripheral compatibility is limited to the evidence in [HARDWARE_SUPPORT.md](../HARDWARE_SUPPORT.md). This review does not certify hostile-image isolation.

The student's active server/VM was not restarted. Backend fixes take effect on the next normal server restart; test servers loaded and exercised the reviewed code separately.
