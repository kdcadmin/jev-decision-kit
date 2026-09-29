"""Generate a 44s kick+clap bed. Local only."""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SR = 44100
DUR = 44.0
BPM = 108.0


def clamp(x: float) -> float:
    return max(-1.0, min(1.0, x))


def kick(n: int) -> list[float]:
    out = []
    for i in range(n):
        t = i / SR
        env = math.exp(-t * 18)
        freq = 90 * math.exp(-t * 8) + 40
        out.append(env * math.sin(2 * math.pi * freq * t))
    return out


def snare(n: int) -> list[float]:
    out = []
    x = 0.17
    for i in range(n):
        t = i / SR
        env = math.exp(-t * 22)
        x = 1.0 - 2.0 * ((x * 9973 + 13) % 10000) / 10000.0
        tone = math.sin(2 * math.pi * 180 * t)
        out.append(env * (0.55 * x + 0.45 * tone))
    return out


def hat(n: int) -> list[float]:
    out = []
    x = 0.31
    for i in range(n):
        t = i / SR
        env = math.exp(-t * 70)
        x = 1.0 - 2.0 * ((x * 7919 + 17) % 10000) / 10000.0
        out.append(0.22 * env * x)
    return out


def main() -> None:
    n = int(SR * DUR)
    mix = [0.0] * n
    beat = 60.0 / BPM
    k = kick(int(SR * 0.28))
    s = snare(int(SR * 0.22))
    h = hat(int(SR * 0.08))
    t = 0.0
    step = 0
    while t < DUR:
        i0 = int(t * SR)
        hit = k if step % 2 == 0 else s
        src = hit
        for j, v in enumerate(src):
            if i0 + j < n:
                mix[i0 + j] += v * (0.95 if step % 2 == 0 else 0.72)
        if step % 2 == 0:
            for j, v in enumerate(h):
                if i0 + j < n:
                    mix[i0 + j] += v
        # off-hat
        i1 = int((t + beat * 0.5) * SR)
        for j, v in enumerate(h):
            if i1 + j < n:
                mix[i1 + j] += v * 0.7
        t += beat
        step += 1

    peak = max(abs(x) for x in mix) or 1.0
    path = Path(__file__).with_name("beat.wav")
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = b"".join(struct.pack("<h", int(clamp(x / peak * 0.86) * 32767)) for x in mix)
        w.writeframes(frames)
    print(path)


if __name__ == "__main__":
    main()
