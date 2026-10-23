"""Unprivileged raw disk inspection. No loop devices, mounts, or guest code."""

import struct
import zlib
from pathlib import Path

MAX_IMAGE = 64 * 1024**3


def regular_file(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Not a regular file: {path}")
    return path


def inspect_raw(path: Path):
    size = path.stat().st_size
    if not 2048 <= size <= MAX_IMAGE:
        raise ValueError("Image must be between 2 KiB and 64 GiB")
    with path.open("rb") as f:

        def read(offset, length):
            if offset < 0 or offset + length > size:
                raise ValueError("Partition extends beyond image")
            f.seek(offset)
            data = f.read(length)
            if len(data) != length:
                raise ValueError("Truncated image")
            return data

        def filesystem(offset, length):
            if length >= 1082 and read(offset + 1080, 2) == b"\x53\xef":
                return "ext4"
            if length >= 512:
                boot = read(offset, 512)
                if boot[510:512] == b"\x55\xaa" and (
                    boot[54:62].startswith(b"FAT") or boot[82:90].startswith(b"FAT")
                ):
                    return "fat"
            return "unknown"

        mbr = read(0, 512)
        partitions = []
        table = "none"
        if read(512, 8) == b"EFI PART":
            table = "gpt"
            header = bytearray(read(512, 512))
            length, crc = struct.unpack_from("<II", header, 12)
            if not 92 <= length <= 512:
                raise ValueError("Invalid GPT header")
            struct.pack_into("<I", header, 16, 0)
            if zlib.crc32(header[:length]) != crc:
                raise ValueError("Invalid GPT header checksum")
            lba, count, entry_size, entries_crc = struct.unpack_from(
                "<QIII", header, 72
            )
            if not 1 <= count <= 4096 or not 128 <= entry_size <= 4096:
                raise ValueError("Unsupported GPT entry table")
            current_lba, backup_lba, first_usable, last_usable = struct.unpack_from(
                "<QQQQ", header, 24
            )
            table_end = (lba * 512 + count * entry_size + 511) // 512
            if (
                current_lba != 1
                or backup_lba != size // 512 - 1
                or lba < 2
                or first_usable < table_end
                or not first_usable <= last_usable < backup_lba
            ):
                raise ValueError("Invalid GPT disk geometry")
            entries = read(lba * 512, count * entry_size)
            if zlib.crc32(entries) != entries_crc:
                raise ValueError("Invalid GPT partition checksum")
            for i in range(count):
                entry = entries[i * entry_size : (i + 1) * entry_size]
                if entry[:16] == bytes(16):
                    continue
                start, end = struct.unpack_from("<QQ", entry, 32)
                if not first_usable <= start <= end <= last_usable:
                    raise ValueError("GPT partition is outside the usable disk area")
                partitions.append(
                    {
                        "number": i + 1,
                        "offset": start * 512,
                        "size_bytes": (end - start + 1) * 512,
                    }
                )
        elif mbr[510:512] == b"\x55\xaa":
            table = "mbr"
            for i in range(4):
                entry = mbr[446 + 16 * i : 462 + 16 * i]
                if not entry[4]:
                    continue
                if entry[4] in (5, 15, 0x85, 0xEE):
                    raise ValueError(
                        "Extended/hybrid MBR is unsupported; use primary MBR or GPT partitions"
                    )
                start, sectors = struct.unpack_from("<II", entry, 8)
                partitions.append(
                    {
                        "number": i + 1,
                        "offset": start * 512,
                        "size_bytes": sectors * 512,
                    }
                )
        if not partitions:
            if filesystem(0, size) != "ext4":
                raise ValueError(
                    "Expected a raw ext4 filesystem or an MBR/GPT disk image (.img, .wic, .sdimg)"
                )
            table = "none"
        previous_end = 512
        for part in sorted(partitions, key=lambda p: p["offset"]):
            start, length = part["offset"], part["size_bytes"]
            if start < previous_end or not length or start + length > size:
                raise ValueError("Invalid, overlapping, or truncated partitions")
            part["filesystem"] = filesystem(start, length)
            previous_end = start + length
        return {"table": table, "size_bytes": size, "partitions": partitions}


def extract_pi_boot(path, layout, destination):
    from pyfatfs.PyFatFS import PyFatFS

    fat = next((p for p in layout["partitions"] if p["filesystem"] == "fat"), None)
    if not fat:
        raise ValueError("Raspberry Pi image needs a FAT boot partition")
    try:
        with PyFatFS(str(path), offset=fat["offset"], read_only=True) as fs:

            def extract(name, required=True):
                if not fs.isfile(name):
                    if required:
                        raise ValueError(f"Pi 3B 64-bit boot file missing: {name}")
                    return ""
                if fs.getsize(name) > 256 * 1024**2:
                    raise ValueError("Boot artifact is too large")
                target = destination / name
                with fs.openbin(name) as source, target.open("wb") as output:
                    import shutil

                    shutil.copyfileobj(source, output)
                return str(target)

            kernel = extract("kernel8.img")
            dtb = extract("bcm2710-rpi-3-b.dtb")
            initrd = extract("initramfs8", required=False)
            if fs.isfile("cmdline.txt") and fs.getsize("cmdline.txt") > 4096:
                raise ValueError("Pi command line exceeds 4096 bytes")
            cmdline = (
                fs.readtext("cmdline.txt").strip()
                if fs.isfile("cmdline.txt")
                else "root=/dev/mmcblk0p2 rootwait rw"
            )
            cmdline = " ".join(
                word
                for word in cmdline.split()
                if not word.startswith("console=")
                and word
                not in (
                    "init=/usr/lib/raspberrypi-sys-mods/firstboot",
                    "init=/usr/lib/raspi-config/init_resize.sh",
                )
            )
            return {
                "profile": "raspi3b",
                "kernel": kernel,
                "dtb": dtb,
                "initrd": initrd,
                "cmdline": f"console=ttyAMA0,115200 {cmdline}",
                "managed": False,
            }
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Cannot read Raspberry Pi boot partition: {exc}") from exc
