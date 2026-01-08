# WindVox

**Linux 智能语音输入服务** - 通过全局快捷键触发录音，调用火山引擎豆包流式语音识别，将语音实时转换为文本并自动输入到当前活动窗口。

## ✨ 功能特性

- 🎤 **语音识别**: 使用火山引擎豆包流式语音识别模型 2.0
- ⌨️ **快捷键触发**: 支持对讲机模式 (按住说话) 和切换模式
- 🖥️ **系统托盘**: 显示服务状态 (待机/录音/处理/错误)
- 🔧 **后台服务**: 作为 systemd 用户服务运行，开机自启
- 🈶 **中文支持**: 完美支持中文输入

## 📋 系统要求

- Ubuntu 22.04 / 24.04 LTS (或其他 Debian 系发行版)
- X11 桌面环境 (Wayland 支持有限)
- Python 3.10+
- 火山引擎账号及豆包语音识别 API 凭证

## 🚀 快速开始

### 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y \
    portaudio19-dev \
    python3-dev \
    python3-venv \
    xdotool \
    gir1.2-ayatanaappindicator3-0.1 \
    libgirepository1.0-dev \
    pkg-config \
    libcairo2-dev
```

### 2. 运行安装脚本

```bash
chmod +x install.sh
./install.sh
```

### 3. 配置凭证

首先，获取火山引擎 API 凭证：**[凭证获取指南](docs/volcengine-credentials.md)**

然后编辑配置文件：

```bash
nano ~/.config/windvox/config.yaml
```

填入你的火山引擎凭证：

```yaml
volcengine:
  app_key: "你的 App ID"
  access_key: "你的 Access Token"
```

### 4. 测试连接

```bash
~/.local/share/windvox/venv/bin/windvox --test-connection
```

### 5. 启动服务

```bash
systemctl --user start windvox
systemctl --user status windvox
```

## 📖 使用方法

| 模式 | 操作 |
|------|------|
| **对讲机模式** (默认) | 按住 F2 说话，松开后自动输入 |
| **切换模式** | 按 F2 开始录音，再按 F2 结束 |

## ⚙️ 配置选项

配置文件位置：`~/.config/windvox/config.yaml`

```yaml
volcengine:
  app_key: "APP_ID"
  access_key: "ACCESS_TOKEN"
  resource_id: "volc.seedasr.sauc.duration"
  ws_url: "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"

interaction:
  trigger_key: "f2"          # 触发键
  mode: "push_to_talk"       # push_to_talk | toggle

audio:
  device_index: null         # null = 默认设备
  sample_rate: 16000
  chunk_duration_ms: 200     # 音频块大小

input:
  typing_delay_ms: 10        # 按键间隔
```

## 🛠️ 命令行选项

```bash
windvox --help              # 显示帮助
windvox --list-devices      # 列出音频设备
windvox --validate-config   # 验证配置
windvox --test-connection   # 测试 ASR 连接
windvox -v                  # 详细日志模式
```

## 📊 服务管理

```bash
# 启动/停止/重启
systemctl --user start windvox
systemctl --user stop windvox
systemctl --user restart windvox

# 查看状态
systemctl --user status windvox

# 查看日志
journalctl --user -u windvox -f

# 禁用开机自启
systemctl --user disable windvox
```

## 🗑️ 卸载

```bash
./uninstall.sh
# 删除配置文件 (可选)
rm -rf ~/.config/windvox
```

## ⚠️ 已知限制

- **Wayland**: 全局热键和键盘模拟在 Wayland 下支持有限，建议使用 X11
- **IDE 兼容性**: 某些 IDE 可能需要增加 `typing_delay_ms`

## 📝 许可证

MIT License