# Hardware support

| Feature | ARM64 virt | Raspberry Pi 3B |
|---|---|---|
| CPU | Cortex-A53, 2 cores, 512 MiB | Cortex-A53, 4 cores, 1 GiB |
| Boot | Direct kernel, optional initramfs/DTB | Direct kernel and Pi 3B DTB extracted from FAT |
| Storage | Virtio block: ext4 or MBR/GPT disk | Emulated SD/MMC, MBR/GPT disk |
| UART | PL011 → host PTY | PL011 → host PTY |
| Network | Virtio Ethernet, NAT, QMP link | USB Ethernet adapter, NAT, QMP link; guest driver required |
| Display | Bundled framebuffer; no browser viewer | Framebuffer model; desktop unvalidated, no browser viewer |
| Expansion | No application GPIO/I²C/SPI driver | No application GPIO/I²C/SPI driver |

Real boot verification: bundled Alpine on virt; partitioned Alpine rootfs with a custom kernel/initramfs on virt; official Raspberry Pi OS Lite Bullseye ARM64 2023-12-05 to UART login on raspi3b, QEMU 9.0.2.

Pi firmware, config.txt, overlays, U-Boot and EFI bootloaders are not executed. Support for one Pi OS image does not imply compatibility with every release or physical-board peripheral. Raspberry Pi 4 remains disabled; Pi 5 and 32-bit images are unsupported. Native Wi-Fi/Bluetooth, GPU acceleration and graphical desktops are not validated.

See [image workflow and limitations](docs/IMAGES.md). All consoles use external host terminals, including VS Code. No browser terminal or framebuffer viewer is provided.

Primary QEMU documentation: [virt](https://www.qemu.org/docs/master/system/arm/virt.html), [Raspberry Pi](https://www.qemu.org/docs/master/system/arm/raspi.html).
