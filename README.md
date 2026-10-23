# Raspberry Pi Virtual Lab

A local ARM64 Linux laboratory for Ubuntu x86_64. FastAPI manages unprivileged QEMU; the web interface controls real power, storage and connections. All shell access runs in an external host terminal, such as the VS Code integrated terminal. There are no browser terminals or console viewers.

The default board is QEMU **virt**, using Cortex-A53 CPUs, virtio storage and Ethernet. Imported disks can select **Raspberry Pi 3B** with SD/MMC; an official 64-bit Pi OS Lite image has been verified to reach UART login. See [custom and SD images](docs/IMAGES.md) for importing Yocto / Buildroot artifacts, boot settings, tested Pi OS versions and hardware limitations.

```bash
./scripts/setup-ubuntu.sh
./scripts/start.sh
```

Open http://127.0.0.1:8000. Create a student disk, insert it, connect UART to host, and power on. In VS Code choose **Terminal → New Terminal**, then paste the UART command displayed in the UI:

```bash
flock -n runtime/uart.lock picocom -b 115200 runtime/uart0
```

Use the absolute paths supplied by the UI, with exactly one UART client at a time. Connect before power-on to watch actual Linux boot output. Disconnecting UART removes the host endpoint, not the emulated PL011 controller.

For SSH, use another VS Code terminal:

```bash
ssh -p 2222 student@127.0.0.1
```

Bundled Alpine login and password: `student` / `student`. Imported images use their own credentials. These commands work in standard host terminals too; VS Code is the documented student workflow. The browser only copies commands and controls hardware, and cannot send guest shell input. Legacy `/api/serial` and `/api/display` WebSocket connections are denied; UART browser mode is rejected.

Guest SSH is prepared during setup, so student boots need no package downloads. Graceful shutdown invokes actual guest poweroff via local management SSH and requires Ethernet connectivity. Reset and forced off can corrupt the student's writable overlay. The base image remains protected. Power off before changing boot media.

Virtio GPU/keyboard hardware remains configured for future graphics work, but the current text framebuffer has no browser viewer. A graphical desktop is not installed. Console logs remain in `runtime/serial.log` and `runtime/qemu.log` for reading from the host terminal.

See [INSTALL.md](INSTALL.md), [ARCHITECTURE.md](ARCHITECTURE.md), [HARDWARE_SUPPORT.md](HARDWARE_SUPPORT.md), [TESTING.md](TESTING.md), and [the first lab](labs/01-first-boot.md).
