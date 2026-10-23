# Lab 1: follow a real boot

1. Create a student disk and insert it with power OFF. Select UART, connect to host, and copy the displayed flock/picocom command into an Ubuntu terminal before turning power on.
2. Find `Linux version`, the PL011 console, virtio disk detection and ext4 mount in boot output. The prepared image already includes SSH and the student account. Log in with `student` / `student`.
3. Run `uname -a`, `cat /proc/cpuinfo`, `cat /proc/mounts`, `ls /sys/class/net`, and `ip addr`. Explain why virtio devices do not make this a Raspberry Pi.
4. Use the displayed SSH command in another terminal. Write `echo hello > ~/persistent.txt`.
5. Disconnect Ethernet in the UI. From UART, run `cat /sys/class/net/eth0/carrier`; expect 0. SSH stops working. Reconnect, check carrier 1 and reconnect SSH.
6. Gracefully shut down. Wait for power OFF, restart, and read `~/persistent.txt`. Eject is refused while powered on.
7. Shut down, reset that student's disk, then boot again. Explain why the file vanished and why the base image was unaffected.

Run all commands in the VS Code integrated terminal, using picocom for UART or ssh for networking. A disconnected cable does not stop the CPU or remove the PL011 controller.

Boot logs can be followed from another VS Code terminal with `tail -f runtime/serial.log`. The UI has no embedded console.
