"""Bridge real QEMU UART bytes to a host PTY; capture boot logs offline."""

import asyncio
import os
import pty
import tty
from pathlib import Path


class SerialBroker:
    def __init__(self, directory: Path):
        self.path = directory / "uart0"
        self.log_path = directory / "serial.log"
        self.mode = "disconnected"
        self.master = self.slave = None
        self.writer = None
        self.history = bytearray()
        self.dropped_host_bytes = 0

    async def attach(self, socket: Path):
        for _ in range(100):
            try:
                reader, self.writer = await asyncio.open_unix_connection(str(socket))
                break
            except OSError:
                await asyncio.sleep(0.1)
        else:
            raise RuntimeError("QEMU serial socket unavailable")
        self.log_path.write_bytes(b"")
        while data := await reader.read(8192):
            with self.log_path.open("ab") as logfile:
                logfile.write(data)
            self.history.extend(data)
            del self.history[:-512_000]
            if self.master is not None:
                try:
                    os.write(self.master, data)
                except (BlockingIOError, OSError):
                    self.dropped_host_bytes += len(data)

    def connect(self, mode: str):
        if mode != "host":
            raise ValueError("UART is available through a host terminal only")
        self.disconnect()
        self.mode = mode
        if mode == "host":
            self.master, self.slave = pty.openpty()
            tty.setraw(self.slave)
            os.chmod(os.ttyname(self.slave), 0o600)
            os.set_blocking(self.master, False)
            self.path.symlink_to(os.ttyname(self.slave))
            asyncio.get_running_loop().add_reader(self.master, self._input)

    def _input(self):
        try:
            data = os.read(self.master, 8192)
        except (BlockingIOError, OSError):
            return
        if self.writer and data:
            self.writer.write(data)

    def disconnect(self):
        if self.master is not None:
            asyncio.get_running_loop().remove_reader(self.master)
            os.close(self.master)
            os.close(self.slave)
        self.master = self.slave = None
        self.path.unlink(missing_ok=True)
        self.mode = "disconnected"

    async def close(self):
        self.disconnect()
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except (ConnectionError, BrokenPipeError):
                pass
        self.writer = None
