# Changelog

All notable changes to WindVox will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-09

### Added
- 初始版本发布
- 🎤 支持火山引擎豆包流式语音识别模型 2.0
- ⌨️ 全局快捷键触发录音 (默认 F2)
- 🔊 对讲机模式 (按住说话) 和切换模式
- 🖥️ 系统托盘图标显示服务状态
- 🈶 完美支持中文输入 (使用 xdotool)
- 🔧 Systemd 用户服务支持，开机自启
- 📝 完整的配置文件支持
- 🛠️ CLI 工具：列出设备、验证配置、测试连接

### Technical Details
- WebSocket 连接使用 `bigmodel_async` 接口（优化版双向流式）
- 音频块大小：200ms（官方推荐值）
- 采样率：16kHz / 16bit / 单声道
- 使用 gzip 压缩音频数据
