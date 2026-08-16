from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
from aiortc import RTCPeerConnection, RTCSessionDescription
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

try:
    from .video import make_vertical_video
except ImportError:  # Docker runs this directory as the import root.
    from video import make_vertical_video


ENGINE_URL = os.getenv("LIVETALKING_URL", "http://127.0.0.1:8010").rstrip("/")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
JOB_DIR = OUTPUT_DIR / "jobs"
JOB_DIR.mkdir(parents=True, exist_ok=True)
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "0.5"))
START_TIMEOUT = int(os.getenv("START_TIMEOUT", "30"))
FINISH_TIMEOUT = int(os.getenv("FINISH_TIMEOUT", "900"))
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
APP_USER = os.getenv("APP_USER", "legal")
security = HTTPBasic()


def require_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    import secrets

    if not APP_PASSWORD:
        raise HTTPException(status_code=503, detail="服务尚未设置 APP_PASSWORD")
    valid_user = secrets.compare_digest(credentials.username.encode(), APP_USER.encode())
    valid_password = secrets.compare_digest(credentials.password.encode(), APP_PASSWORD.encode())
    if not (valid_user and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


class GenerateRequest(BaseModel):
    text: str = Field(min_length=10, max_length=5000)
    avatar: str = Field(default="wav2lip256_avatar1", min_length=1, max_length=100)
    voice: str = Field(default="zh-CN-YunxiaNeural", min_length=1, max_length=100)
    title: str = Field(default="一分钟法律科普", min_length=1, max_length=40)
    disclaimer: str = Field(default="AI生成｜一般性法律科普，不构成个案法律意见", max_length=80)


@dataclass
class Job:
    id: str
    status: str = "queued"
    message: str = "等待处理"
    file_name: str | None = None


app = FastAPI(title="法律 AI 数字人", version="0.1.0")
jobs: dict[str, Job] = {}


def save_job(job: Job) -> None:
    target = JOB_DIR / f"{job.id}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(job), ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)


def load_jobs() -> None:
    for path in JOB_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            job = Job(**data)
            if job.status in {"queued", "running"}:
                job.status = "failed"
                job.message = "服务重启导致任务中断，请重新提交"
                save_job(job)
            jobs[job.id] = job
        except (OSError, ValueError, TypeError):
            continue


load_jobs()


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
        save_job(job)
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
            save_job(job)
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
            raw_name = f"{job_id}-raw.mp4"
            raw_path = OUTPUT_DIR / raw_name
            raw_path.write_bytes(video.content)
            file_name = f"{job_id}.mp4"
            job.message = "正在生成 9:16 竖屏、字幕和免责声明"
            save_job(job)
            await make_vertical_video(raw_path, OUTPUT_DIR / file_name, request.text, request.title, request.disclaimer)
            raw_path.unlink(missing_ok=True)
            job.file_name = file_name
            job.status = "complete"
            job.message = "生成完成"
            save_job(job)
    except Exception as exc:  # noqa: BLE001 - job errors are returned to the UI
        job.status = "failed"
        job.message = str(exc)
        save_job(job)
    finally:
        await peer.close()


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
async def index() -> str:
    return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


@app.get("/health", dependencies=[Depends(require_auth)])
async def health() -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(ENGINE_URL)
            engine_ok = response.status_code < 500
        except httpx.HTTPError:
            engine_ok = False
    return {"app": "ok", "engine": "ok" if engine_ok else "unreachable", "engine_url": ENGINE_URL}


@app.post("/api/jobs", status_code=202, dependencies=[Depends(require_auth)])
async def create_job(request: GenerateRequest, background_tasks: BackgroundTasks) -> dict:
    job_id = uuid.uuid4().hex
    jobs[job_id] = Job(id=job_id)
    save_job(jobs[job_id])
    background_tasks.add_task(run_job, job_id, request)
    return asdict(jobs[job_id])


@app.get("/api/jobs/{job_id}", dependencies=[Depends(require_auth)])
async def get_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    result = asdict(job)
    if job.file_name:
        result["download_url"] = f"/api/jobs/{job_id}/download"
    return result


@app.get("/api/jobs/{job_id}/download", dependencies=[Depends(require_auth)])
async def download(job_id: str) -> FileResponse:
    job = jobs.get(job_id)
    if not job or job.status != "complete" or not job.file_name:
        raise HTTPException(status_code=404, detail="视频尚未生成")
    return FileResponse(OUTPUT_DIR / job.file_name, media_type="video/mp4", filename="legal-avatar.mp4")
