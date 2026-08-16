# 法律 AI 数字人 MVP

这是 `LiveTalking` 的短视频生成控制层。它在云 GPU 上连接 LiveTalking，自动完成：建立 WebRTC 会话、提交中文口播、开始/停止录制、等待播报完成和下载 MP4。

## 推荐配置

- Ubuntu 22.04
- NVIDIA RTX 3090 24GB
- CUDA 12.x 与匹配的 PyTorch
- LiveTalking 使用 MuseTalk；首次验证也可使用 Wav2Lip

GT 730 电脑只负责打开网页和下载成片，不参与模型推理。

## 启动

1. 按上游 README 在云 GPU 启动 LiveTalking，确认 `http://127.0.0.1:8010` 可访问。
2. 创建访问密码并启动控制层：

```bash
cp .env.example .env
# 编辑 .env，把 APP_PASSWORD 换成至少 16 位随机密码
docker compose up -d --build
```

3. 浏览器打开 `http://云服务器IP:7860`，用 `.env` 里的账号密码登录，填写文案、数字人 ID、声音、标题和免责声明后生成视频。

若 LiveTalking 在另一台服务器：

```bash
LIVETALKING_URL=http://GPU服务器IP:8010 docker compose up -d --build
```

## 健康检查

```bash
curl http://127.0.0.1:7860/health
```

健康检查同样需要 Basic Auth。`engine` 为 `ok` 才能生成视频：

```bash
curl -u legal:你的密码 http://127.0.0.1:7860/health
```

## 上线前检查

- 只使用本人或已获书面授权的人物形象与声音。
- 法律文案发布前必须由具备相应能力的人复核，并记录核验日期。
- 不使用“包赢”“保证获赔”等承诺性表达。
- 抖音发布时主动声明 AI 生成内容。
- 遵守 LiveTalking、MuseTalk、TTS 模型及模型权重各自的许可证和署名要求。

## 当前边界

- 成片会自动转换为 1080×1920、添加中文字幕、标题和底部免责声明。
- 任务元数据会持久化到 `outputs/jobs`；服务重启时，未完成任务会被标记为中断，已完成视频仍可下载。
- 本项目不把模型权重和人物素材提交到 GitHub。

## RunPod 云 GPU

完整的从零部署步骤位于 [`../deploy/runpod/README.md`](../deploy/runpod/README.md)，包括模型下载、数字人形象创建、服务启动和日常关机流程。

仓库中的 `assets/default-legal-presenter.png` 是 AI 生成的虚构人物，只用于默认样片和部署验证，不代表律师、司法机关或其他真实身份。
