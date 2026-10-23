"""Capabilities describe actual hardware, host adapters, and unavailable features."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Peripheral:
    id: str
    device_type: str
    display_name: str
    connector: str
    category: str
    driver: str
    capabilities: tuple[str, ...]
    limitation: str
    supported_profiles: tuple[str, ...] = ("virt-arm64",)


PERIPHERALS = [
    Peripheral(
        "uart0",
        "UART",
        "UART adapter",
        "UART",
        "QEMU hardware + host adapter",
        "serial-broker",
        ("connect", "disconnect", "host-PTY"),
        "115200 8N1 is nominal: a virtual byte stream has no physical baud timing. Host terminal access only; no browser console.",
    ),
    Peripheral(
        "boot0",
        "Storage",
        "Virtio boot media",
        "virtio",
        "QEMU hardware",
        "virtio-blk",
        ("create", "insert", "eject", "reset", "inspect"),
        "Raw ext4 or MBR/GPT disks. Virtio on ARM64 virt; real emulated SD/MMC on Raspberry Pi 3B. Power off before changing media.",
    ),
    Peripheral(
        "net0",
        "Networking",
        "Virtio Ethernet",
        "Ethernet",
        "QEMU hardware",
        "QMP set_link",
        ("connect", "disconnect", "NAT", "SSH"),
        "User networking; guest address is not probed. No TAP or host networking changes.",
    ),
    Peripheral(
        "display0",
        "Display",
        "Monitor and keyboard",
        "display",
        "QEMU hardware",
        "virtio-gpu (host only)",
        (),
        "Real virtio GPU and keyboard remain installed. In-browser consoles are disabled; use a host terminal for UART or SSH. No desktop is installed.",
    ),
    Peripheral(
        "gpio0",
        "GPIO",
        "GPIO / I²C / SPI",
        "header",
        "unavailable",
        "none",
        (),
        "Expansion peripherals are not implemented. Connector drawing does not emulate pins.",
    ),
]
PROFILES = [
    {
        "id": "virt-arm64",
        "name": "Generic ARM64 Educational Board",
        "machine": "virt",
        "cpu": "Cortex-A53",
        "memory_mib": 512,
        "cores": 2,
        "supported": True,
        "limitations": "Generic QEMU platform, not Raspberry Pi. PL011 UART, virtio storage and Ethernet. Direct kernel boot; no bootloader. Virtio GPU framebuffer and keyboard, without a desktop.",
    },
    {
        "id": "raspi3b",
        "name": "Raspberry Pi 3B",
        "machine": "raspi3b",
        "cpu": "Cortex-A53",
        "memory_mib": 1024,
        "cores": 4,
        "supported": True,
        "limitations": "64-bit Pi 3B direct kernel boot from FAT artifacts; SD/MMC and USB Ethernet. Firmware/config.txt and overlays are not executed. Compatibility depends on the image kernel; no browser console.",
    },
    {
        "id": "raspi4b",
        "name": "Raspberry Pi 4B",
        "supported": False,
        "limitations": "Not validated. QEMU documentation lists missing PCIe and GENET Ethernet.",
    },
]


def peripherals():
    return [asdict(p) for p in PERIPHERALS]
