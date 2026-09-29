"""40s kick bed. Local only."""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SR = 44100
DUR = 40.0
BPM = 118.0


def clamp(x: float) -> float:
    return max(-1.0, min(1.0, x))


def main() -> None:
    n = int(SR * DUR)
    mix = [0.0] * n
    beat = 60.0 / BPM
    t = 0.0
    step = 0
    x = 0.13
    while t < DUR:
        i0 = int(t * SR)
        for i in range(int(SR * 0.22)):
            if i0 + i >= n:
                break
            tt = i / SR
            if step % 2 == 0:
                env = math.exp(-tt * 16)
                freq = 88 * math.exp(-tt * 7) + 38
                mix[i0 + i] += env * math.sin(2 * math.pi * freq * tt)
            else:
                env = math.exp(-tt * 20)
                x = 1.0 - 2.0 * ((x * 9973 + 13) % 10000) / 10000.0
                mix[i0 + i] += env * (0.5 * x + 0.4 * math.sin(2 * math.pi * 190 * tt))
        t += beat
        step += 1
    peak = max(abs(v) for v in mix) or 1.0
    path = Path(__file__).with_name("beat.wav")
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(clamp(v / peak * 0.84) * 32767)) for v in mix))
    print(path)


if __name__ == "__main__":
    main()
