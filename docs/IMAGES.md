# Boot your own disk image

Storage images accepts uncompressed raw `.img`, `.wic`, `.sdimg`, `.raw`, and `.ext4` files up to 64 GiB. The contents determine the format: a standalone ext4 filesystem, primary MBR partitions, or GPT with valid checksums. Extended MBR partitions, qcow2 uploads and compressed archives are unsupported. Decompress `.xz`, `.gz` or `.zip` first.

Open **Storage images → Import disk image**. Choose the target board, then supply an absolute path on the computer running the backend or choose a file in the browser. Paths may point to build-output symlinks. The source must be a regular file, not a block device. Finish the build before importing; don't rewrite the source during the copy.

Import creates a private baseline and writable qcow2 overlay. It does not write to your build output. Guest writes persist across boots. **Reset** discards guest writes and restores the imported baseline, retaining boot settings. Rebuilding the source does not update an existing import: import the new build as another disk.

Power off before importing, changing settings, inserting, ejecting, resetting or deleting. To delete an image, eject it first and choose **Delete**, then confirm. This removes its private disk copies and saved boot artifacts; source build files are preserved. The inserted disk selects the emulated board. All console access stays in the VS Code terminal; no browser console is provided.

## Yocto / Buildroot: ARM64 virt

Build for QEMU `virt`, AArch64 / Cortex-A53, using PL011 UART. A build for a real Raspberry Pi or an x86 machine is not compatible with this target merely because the filesystem is ext4.

1. Import the rootfs or complete partitioned disk using **ARM64 virt**.
2. Expand its **Boot settings**. Enter the host path to your kernel (`Image` or compatible QEMU-loadable kernel), and optional initramfs and DTB. Saved files are copied into the lab. Blank path fields preserve the saved artifact; check **No initramfs** or **Use QEMU DTB** to remove one.
3. Set the Linux command line. Examples:

   ```text
   console=ttyAMA0,115200 root=/dev/vda rw
   console=ttyAMA0,115200 root=/dev/vda2 rootwait rw
   ```

   The first uses a whole-disk root filesystem; the second uses partition 2. Inspect the image layout and use the actual root partition. Automatic detection suggests the first ext4 partition, which may not be your intended rootfs.
4. Save, insert, connect UART to host, then power on.

Your kernel or initramfs must provide virtio PCI, virtio block, ext4, PL011 and any required networking drivers. Your initramfs must honor the root device in the command line. The lab's bundled Alpine initramfs hardcodes `/dev/vda`; it is not a generic initramfs for partitioned/custom images. Leave DTB empty to use QEMU's generated virt device tree.

Typical build artifacts are Buildroot `output/images/rootfs.ext4`, `Image` and `sdcard.img`, or Yocto `tmp/deploy/images/<machine>/` rootfs, `.wic` and kernel outputs, depending on the build configuration. This is direct kernel boot: boot sectors, U-Boot and EFI inside an imported disk are not executed.

## Official Raspberry Pi OS: Raspberry Pi 3B, 64-bit

Choose **Raspberry Pi 3B** and import a decompressed ARM64 SD image that includes Pi 3B support. The lab extracts `kernel8.img`, `bcm2710-rpi-3-b.dtb`, optional `initramfs8`, and `cmdline.txt` from the FAT boot partition. It uses the real QEMU `raspi3b` machine with four Cortex-A53 cores, 1 GiB RAM and an emulated SD/MMC controller. The virtual card capacity is rounded up to a power of two as required by QEMU; the original partition layout and source image are retained.

The copied command line uses PL011 `console=ttyAMA0,115200`. The stock one-shot `init=/usr/lib/raspberrypi-sys-mods/firstboot` and legacy `init_resize.sh` overrides are removed: they edit boot-partition configuration and rely on firmware re-reading it after reboot, whereas this app boots the copied kernel directly. The lab does not automatically grow the root filesystem. `config.txt`, device-tree overlays and firmware first-run customization scripts are not executed. Review **Boot settings** to override extracted artifacts or command line.

Validated on this host: official **2023-12-05 Raspberry Pi OS Lite Bullseye ARM64**, using QEMU 9.0.2, reaches the serial login prompt. This proves that image boots; it does not certify every Pi OS release, desktop rendering, GPU acceleration, Wi-Fi, Bluetooth or GPIO. Pi 4/5-only images and 32-bit Pi OS are not supported. Raspberry Pi 4 remains disabled. QEMU hardware support: https://www.qemu.org/docs/master/system/arm/raspi.html

Use credentials configured in your own image. Recent official images may require creating a user; there is no lab-injected `student` account, root key or automatic SSH setup. The copied SSH command uses `YOUR_USER`; replace it and enable SSH in the guest. Networking uses an emulated USB Ethernet adapter, not the physical Pi Ethernet chip; guest driver support is required.

For custom images, run `sudo poweroff` (or the appropriate guest command) in the VS Code UART/SSH terminal. The web **Shut down** button is disabled because the lab's management key is only provisioned in its bundled Alpine image. Forced off and hardware reset interrupt writes. Desktop access is not added to the web UI.
