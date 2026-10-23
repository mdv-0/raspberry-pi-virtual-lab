"""Private, serialized QEMU Machine Protocol transport."""

import asyncio
import json
from pathlib import Path


class QMP:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.reader = None
        self.writer = None
        self.events = []

    async def connect(self, path: Path):
        for _ in range(100):
            try:
                self.reader, self.writer = await asyncio.open_unix_connection(str(path))
                await self.reader.readline()
                await self.execute("qmp_capabilities")
                return
            except (OSError, ConnectionError):
                await asyncio.sleep(0.1)
        raise RuntimeError("QMP did not become available")

    async def execute(self, command: str, arguments=None):
        async with self.lock:
            if self.writer is None:
                raise RuntimeError("QMP is unavailable")
            self.writer.write(
                json.dumps({"execute": command, "arguments": arguments or {}}).encode()
                + b"\n"
            )
            await self.writer.drain()
            while True:
                raw = await asyncio.wait_for(self.reader.readline(), 10)
                if not raw:
                    raise RuntimeError("QMP disconnected")
                reply = json.loads(raw)
                if "event" in reply:
                    self.events.append(reply)
                    self.events = self.events[-100:]
                elif "error" in reply:
                    raise RuntimeError(str(reply["error"]))
                elif "return" in reply:
                    return reply["return"]

    async def close(self):
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except (ConnectionError, BrokenPipeError):
                pass
        self.writer = None
