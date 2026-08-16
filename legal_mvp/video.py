from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path


def ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def subtitle_chunks(text: str, width: int = 16) -> list[str]:
    compact = re.sub(r"\s+", "", text)
    sentences = [item for item in re.split(r"(?<=[。！？；])", compact) if item]
    chunks: list[str] = []
    for sentence in sentences:
        chunks.extend(sentence[index : index + width] for index in range(0, len(sentence), width))
    return chunks or [compact]


def ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, rest = divmod(centiseconds, 360000)
    minutes, rest = divmod(rest, 6000)
    whole_seconds, cs = divmod(rest, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{cs:02d}"


def ass_escape(value: str) -> str:
    return value.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def write_ass(path: Path, text: str, duration: float) -> None:
    chunks = subtitle_chunks(text)
    weights = [max(1, len(item)) for item in chunks]
    total = sum(weights)
    cursor = 0.0
    dialogues: list[str] = []
    for index, chunk in enumerate(chunks):
        end = duration if index == len(chunks) - 1 else cursor + duration * weights[index] / total
        dialogues.append(
            f"Dialogue: 0,{ass_time(cursor)},{ass_time(end)},Subtitle,,0,0,0,,{ass_escape(chunk)}"
        )
        cursor = end
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Subtitle,Noto Sans CJK SC,58,&H00FFFFFF,&H000000FF,&H00101010,&H90000000,-1,0,0,0,100,100,1,0,1,4,1,2,70,70,250,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    path.write_text(header + "\n".join(dialogues) + "\n", encoding="utf-8")


async def make_vertical_video(raw: Path, output: Path, text: str, title: str, disclaimer: str) -> None:
    duration = ffprobe_duration(raw)
    subtitle = raw.with_suffix(".ass")
    write_ass(subtitle, text, duration)
    safe_title = title.replace("'", "’").replace(":", r"\:")
    safe_disclaimer = disclaimer.replace("'", "’").replace(":", r"\:")
    filter_graph = (
        "[0:v]split=2[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=28[bg2];"
        "[fg]scale=1000:1450:force_original_aspect_ratio=decrease[fg2];"
        "[bg2][fg2]overlay=(W-w)/2:(H-h)/2-70,"
        f"ass='{subtitle.name}',"
        f"drawtext=font='Noto Sans CJK SC':text='{safe_title}':fontcolor=white:fontsize=68:x=(w-text_w)/2:y=110:borderw=4:bordercolor=black@0.7,"
        f"drawtext=font='Noto Sans CJK SC':text='{safe_disclaimer}':fontcolor=white@0.85:fontsize=30:x=(w-text_w)/2:y=h-90:borderw=2:bordercolor=black@0.7[v]"
    )
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(raw), "-filter_complex", filter_graph,
        "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output),
        cwd=raw.parent,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(f"FFmpeg 竖屏处理失败：{stderr.decode(errors='replace')[-1200:]}")
    subtitle.unlink(missing_ok=True)
