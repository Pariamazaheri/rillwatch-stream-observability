"""Bounded newline framing independent of TCP packet boundaries."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Frame:
    raw: bytes
    error: str | None = None


class Framer:
    def __init__(self, limit=65536):
        if limit < 1:
            raise ValueError("limit must be positive")
        self.limit = limit
        self.buffer = bytearray()
        self.discarding = False

    def feed(self, chunk):
        result = []
        parts = chunk.split(b"\n")
        for index, part in enumerate(parts):
            ended = index < len(parts) - 1
            if not self.discarding:
                space = self.limit - len(self.buffer)
                self.buffer.extend(part[:space])
                if len(part) > space:
                    result.append(Frame(bytes(self.buffer), "frame_too_large"))
                    self.buffer.clear()
                    self.discarding = True
            if ended:
                if not self.discarding:
                    result.append(Frame(bytes(self.buffer)))
                self.buffer.clear()
                self.discarding = False
        return result

    def finish(self):
        result = [Frame(bytes(self.buffer), "incomplete_frame")] if self.buffer else []
        self.buffer.clear()
        self.discarding = False
        return result
