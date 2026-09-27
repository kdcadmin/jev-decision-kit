# Build a short captioned intro from the desktop screenshots.
import subprocess
from pathlib import Path

ROOT = Path(r"D:\jev-decision-kit\intro")
FRAMES = ROOT / "frames"
FONT = "C\\:/Windows/Fonts/msyh.ttc"
OUT = ROOT / "技能柜介绍.mp4"

SHOTS = [
    ("01-cabinet.png", "239 个技能按分类放着。这里改的是副本，原来的文件夹还在。", 7),
    ("03-weights.png", "试了一句查茅台。自己想 1，调用技能 99。行情 98，带上 stock-watch。", 8),
    ("04-calls.png", "这次调用记下来了。可以删掉技能、再加一个，或删掉这一行。", 7),
    ("02-library.png", "库是网上的仓库。介绍译成中文。整仓能装，也可以只装其中一个。", 8),
]


def run(args: list[str]) -> None:
    subprocess.run(args, check=True)


def card(name: str, lines: list[tuple[str, int, int]], seconds: int) -> Path:
    path = FRAMES / name
    draws = []
    for text, size, y in lines:
        draws.append(
            "drawtext=fontfile='"
            + FONT
            + f"':text='{text}':fontsize={size}:fontcolor=0x1c211c:x=(w-text_w)/2:y={y}"
        )
    run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0xe4e1d8:s=1920x1080:r=25:d={seconds}",
            "-vf", ",".join(draws),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
            str(path),
        ]
    )
    return path


def shot(name: str, caption: str, seconds: int) -> Path:
    src = FRAMES / name
    path = FRAMES / f"seg-{name}.mp4"
    vf = (
        f"[0:v]scale=1600:900:flags=lanczos[fg];"
        f"[1:v][fg]overlay=(W-w)/2:28,"
        f"drawbox=x=80:y=948:w=1760:h=96:color=0xf7f6f2@1:t=fill,"
        f"drawtext=fontfile='{FONT}':text='{caption}':fontsize=34:fontcolor=0x1c211c:x=(w-text_w)/2:y=978"
    )
    run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(src),
            "-f", "lavfi", "-i", f"color=c=0xe4e1d8:s=1920x1080:r=25:d={seconds}",
            "-filter_complex", vf,
            "-t", str(seconds),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
            str(path),
        ]
    )
    return path


def main() -> None:
    parts = [
        card("seg-title.mp4", [("技能柜", 84, 430), ("一句话，决定自己想，还是调用技能", 36, 560)], 4),
    ]
    parts += [shot(*item) for item in SHOTS]
    parts.append(card("seg-end.mp4", [("龙虾和 Hermes 读的就是这份柜", 48, 490)], 4))
    listing = FRAMES / "list.txt"
    listing.write_text("".join(f"file '{path.as_posix()}'\n" for path in parts), encoding="utf-8")
    silent = FRAMES / "seg-all.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(silent)])
    run(
        [
            "ffmpeg", "-y",
            "-i", str(silent),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            str(OUT),
        ]
    )
    print(OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
