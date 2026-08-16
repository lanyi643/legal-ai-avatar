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
2. 在本目录启动控制层：

```bash
docker compose up -d --build
```

3. 浏览器打开 `http://云服务器IP:7860`，填写文案、数字人 ID 和声音后生成视频。

若 LiveTalking 在另一台服务器：

```bash
LIVETALKING_URL=http://GPU服务器IP:8010 docker compose up -d --build
```

## 健康检查

```bash
curl http://127.0.0.1:7860/health
```

`engine` 为 `ok` 才能生成视频。

## 上线前检查

- 只使用本人或已获书面授权的人物形象与声音。
- 法律文案发布前必须由具备相应能力的人复核，并记录核验日期。
- 不使用“包赢”“保证获赔”等承诺性表达。
- 抖音发布时主动声明 AI 生成内容。
- 遵守 LiveTalking、MuseTalk、TTS 模型及模型权重各自的许可证和署名要求。

## 当前边界

- 成片保持 LiveTalking 的原始录制尺寸；9:16 裁切、字幕和封面建议在下一阶段用 FFmpeg 模板完成。
- 任务状态暂存在内存中，服务重启后会清空；生产环境应接 Redis 或数据库。
- 本项目不把模型权重和人物素材提交到 GitHub。
