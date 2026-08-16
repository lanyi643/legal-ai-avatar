# RunPod 部署：从零到可生成视频

RunPod 的 Pod 由平台直接运行容器，不支持在 Pod 内使用 Docker Compose。本目录因此提供单机安装与双进程启动脚本。只需要对外开放 HTTP 端口 `7860`（法律视频控制台）和 `8010`（数字人形象创建页）。

## 1. 创建 Pod

1. 注册并登录 RunPod；充值由账户本人完成。
2. 创建 GPU Pod，优先选择 RTX 3090 24GB；没有库存时选择 A40 48GB 或 RTX 4090 24GB。
3. 使用官方 PyTorch 模板，Ubuntu 22.04/24.04、CUDA 12.8 均可。
4. Container Disk 建议 50GB，Network Volume 建议 50GB 并挂载到 `/workspace`。
5. 暴露 HTTP 端口 `7860` 和 `8010`。

网络卷应在创建 Pod 时挂载，之后不能直接附加到已有 Pod。模型和成片保存在 `/workspace`，停止计算后仍可保留；删除 Pod 前仍要核对平台的存储设置。

## 2. 安装

在 Pod 的 Web Terminal 中运行：

```bash
cd /workspace
git clone --branch agent/legal-video-mvp https://github.com/lanyi643/legal-ai-avatar.git
cd legal-ai-avatar
bash deploy/runpod/install.sh
```

安装会下载 PyTorch、LiveTalking 依赖及 MuseTalk 1.5 官方权重。首次安装时间取决于机房网络。

## 3. 创建数字人形象

先临时启动引擎：

```bash
source /workspace/legal-ai-avatar-venv/bin/activate
cd /workspace/legal-ai-avatar
python app.py --transport webrtc --model musetalk --avatar_id legal_avatar --listenport 8010
```

打开 RunPod 提供的 `8010` HTTP Proxy URL，在地址末尾加 `/avatar.html`。上传本人或已获授权的正面口播视频，数字人 ID 填 `legal_avatar`。素材建议：

- 10–30 秒、25fps、正面半身；
- 光线稳定，嘴部无遮挡；
- 保持自然眨眼和轻微动作；
- 不使用法徽、警徽或可能导致身份误认的场景。

形象创建完成后，在终端按 `Ctrl+C` 停止临时引擎。

## 4. 正式启动

```bash
cd /workspace/legal-ai-avatar
export APP_USER=legal
export APP_PASSWORD='换成至少16位随机密码'
export AVATAR_ID=legal_avatar
bash deploy/runpod/start.sh
```

打开 RunPod 提供的 `7860` HTTP Proxy URL，用上面的账号密码登录。粘贴已核验的法律文案，点击“生成视频”，完成后下载 MP4。

## 5. 日常使用

1. 启动 Pod。
2. 在 Web Terminal 执行第 4 节命令。
3. 打开 `7860` Proxy URL 生成视频。
4. 下载所有成片。
5. 停止 Pod，避免继续产生 GPU 费用。

## 6. 排错

```bash
tail -n 200 /workspace/legal-avatar-logs/engine.log
curl -u legal:你的密码 http://127.0.0.1:7860/health
nvidia-smi
df -h /workspace
```

健康检查中的 `engine` 必须是 `ok`。不要把密码、GitHub Token、支付信息或未授权的人物素材提交到仓库。
