from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
from aiortc import RTCPeerConnection, RTCSessionDescription
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field


ENGINE_URL = os.getenv("LIVETALKING_URL", "http://127.0.0.1:8010").rstrip("/")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "0.5"))
START_TIMEOUT = int(os.getenv("START_TIMEOUT", "30"))
FINISH_TIMEOUT = int(os.getenv("FINISH_TIMEOUT", "900"))


class GenerateRequest(BaseModel):
    text: str = Field(min_length=10, max_length=5000)
    avatar: str = Field(default="wav2lip256_avatar1", min_length=1, max_length=100)
    voice: str = Field(default="zh-CN-YunxiaNeural", min_length=1, max_length=100)


@dataclass
class Job:
    id: str
    status: str = "queued"
    message: str = "等待处理"
    file_name: str | None = None


app = FastAPI(title="法律 AI 数字人", version="0.1.0")
jobs: dict[str, Job] = {}


async def engine_json(client: httpx.AsyncClient, path: str, payload: dict) -> dict:
    response = await client.post(f"{ENGINE_URL}{path}", json=payload)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and data.get("code", 0) != 0:
        raise RuntimeError(data.get("msg") or f"LiveTalking {path} 调用失败")
    return data


async def wait_for_speech(client: httpx.AsyncClient, session_id: str) -> None:
    started = False
    loop = asyncio.get_running_loop()
    start_deadline = loop.time() + START_TIMEOUT
    finish_deadline = loop.time() + FINISH_TIMEOUT
    while loop.time() < finish_deadline:
        data = await engine_json(client, "/is_speaking", {"sessionid": session_id})
        speaking = bool(data.get("data"))
        if speaking:
            started = True
        elif started:
            return
        elif loop.time() > start_deadline:
            raise TimeoutError("数字人未在规定时间内开始播报")
        await asyncio.sleep(POLL_SECONDS)
    raise TimeoutError("数字人播报超时")


async def run_job(job_id: str, request: GenerateRequest) -> None:
    job = jobs[job_id]
    peer = RTCPeerConnection()
    try:
        job.status = "running"
        job.message = "正在连接数字人引擎"
        peer.addTransceiver("audio", direction="recvonly")
        peer.addTransceiver("video", direction="recvonly")
        offer = await peer.createOffer()
        await peer.setLocalDescription(offer)

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=FINISH_TIMEOUT)) as client:
            response = await client.post(
                f"{ENGINE_URL}/whep",
                params={"avatar": request.avatar, "refaudio": request.voice},
                content=peer.localDescription.sdp,
                headers={"Content-Type": "application/sdp"},
            )
            response.raise_for_status()
            session_id = response.headers.get("X-Session-ID")
            if not session_id:
                raise RuntimeError("LiveTalking 未返回 X-Session-ID")
            await peer.setRemoteDescription(RTCSessionDescription(sdp=response.text, type="answer"))

            job.message = "正在生成口播视频"
            await engine_json(client, "/record", {"sessionid": session_id, "type": "start_record"})
            await engine_json(
                client,
                "/human",
                {
                    "sessionid": session_id,
                    "text": request.text,
                    "type": "echo",
                    "interrupt": False,
                    "tts": {"voice": request.voice},
                },
            )
            await wait_for_speech(client, session_id)
            await engine_json(client, "/record", {"sessionid": session_id, "type": "end_record"})

            video = await client.get(f"{ENGINE_URL}/record/{session_id}")
            video.raise_for_status()
            file_name = f"{job_id}.mp4"
            (OUTPUT_DIR / file_name).write_bytes(video.content)
            job.file_name = file_name
            job.status = "complete"
            job.message = "生成完成"
    except Exception as exc:  # noqa: BLE001 - job errors are returned to the UI
        job.status = "failed"
        job.message = str(exc)
    finally:
        await peer.close()


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


@app.get("/health")
async def health() -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(ENGINE_URL)
            engine_ok = response.status_code < 500
        except httpx.HTTPError:
            engine_ok = False
    return {"app": "ok", "engine": "ok" if engine_ok else "unreachable", "engine_url": ENGINE_URL}


@app.post("/api/jobs", status_code=202)
async def create_job(request: GenerateRequest, background_tasks: BackgroundTasks) -> dict:
    job_id = uuid.uuid4().hex
    jobs[job_id] = Job(id=job_id)
    background_tasks.add_task(run_job, job_id, request)
    return asdict(jobs[job_id])


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    result = asdict(job)
    if job.file_name:
        result["download_url"] = f"/api/jobs/{job_id}/download"
    return result


@app.get("/api/jobs/{job_id}/download")
async def download(job_id: str) -> FileResponse:
    job = jobs.get(job_id)
    if not job or job.status != "complete" or not job.file_name:
        raise HTTPException(status_code=404, detail="视频尚未生成")
    return FileResponse(OUTPUT_DIR / job.file_name, media_type="video/mp4", filename="legal-avatar.mp4")
