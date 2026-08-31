"""Incrementally decode only the first JSON answer string; never interpret analysis."""

import json
import re
from collections.abc import Callable


class AnswerStream:
    # This is JSON framing, not a natural-language tool/routing protocol.
    _header = re.compile(r'^\s*\{\s*"answer"\s*:\s*"')

    def __init__(self, emit: Callable[[str], None]):
        self.emit = emit
        self.prefix = ""
        self.started = self.done = False
        self.escape = ""
        self.high_surrogate = ""
        self.length = 0

    def feed(self, part: str) -> None:
        if self.done:
            return
        if not self.started:
            self.prefix += part
            match = self._header.match(self.prefix)
            if not match:
                if len(self.prefix) > 256:
                    self.done = True  # Different key order: full validation fallback.
                    self.prefix = ""
                return
            part = self.prefix[match.end():]
            self.prefix = ""
            self.started = True
        output = []
        for char in part:
            if self.escape:
                self.escape += char
                if self.escape == "\\u" or (self.escape.startswith("\\u") and len(self.escape) < 6):
                    continue
                char = json.loads('"' + self.escape + '"')
                self.escape = ""
            elif char == "\\":
                self.escape = char
                continue
            elif char == '"':
                if self.high_surrogate:
                    raise ValueError("Unpaired Unicode surrogate")
                self.done = True
                break
            elif ord(char) < 32:
                raise ValueError("Unescaped JSON control character")
            if self.high_surrogate:
                if not 0xDC00 <= ord(char) <= 0xDFFF:
                    raise ValueError("Unpaired Unicode surrogate")
                char = chr(0x10000 + ((ord(self.high_surrogate) - 0xD800) << 10) + ord(char) - 0xDC00)
                self.high_surrogate = ""
            elif 0xD800 <= ord(char) <= 0xDBFF:
                self.high_surrogate = char
                continue
            elif 0xDC00 <= ord(char) <= 0xDFFF:
                raise ValueError("Unpaired Unicode surrogate")
            self.length += 1
            if self.length > 64000:
                raise ValueError("Answer exceeds limit")
            output.append(char)
        if output:
            self.emit("".join(output))
