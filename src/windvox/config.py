"""Configuration management for WindVox."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import yaml


@dataclass
class VolcengineConfig:
    """Volcengine API configuration."""
    app_key: str = ""
    access_key: str = ""
    resource_id: str = "volc.seedasr.sauc.duration"
    ws_url: str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"


@dataclass
class InteractionConfig:
    """User interaction configuration."""
    trigger_key: str = "f2"
    mode: Literal["push_to_talk", "toggle"] = "push_to_talk"


@dataclass
class AudioConfig:
    """Audio capture configuration."""
    device_index: Optional[int] = None
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: int = 200  # 200ms chunks (recommended)


@dataclass
class InputConfig:
    """Keyboard input simulation configuration."""
    typing_delay_ms: int = 10


@dataclass
class Config:
    """Main configuration container."""
    volcengine: VolcengineConfig = field(default_factory=VolcengineConfig)
    interaction: InteractionConfig = field(default_factory=InteractionConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    input: InputConfig = field(default_factory=InputConfig)


def get_config_path() -> Path:
    """Get the configuration file path."""
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_dir / "windvox" / "config.yaml"


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from YAML file.
    
    Args:
        config_path: Optional path to config file. Uses default if not specified.
        
    Returns:
        Loaded configuration object.
        
    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If required fields are missing.
    """
    if config_path is None:
        config_path = get_config_path()
    
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Please create it from config.yaml.example"
        )
    
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    config = Config()
    
    # Load volcengine config
    if "volcengine" in data:
        vc = data["volcengine"]
        config.volcengine = VolcengineConfig(
            app_key=str(vc.get("app_key", "")),
            access_key=str(vc.get("access_key", "")),
            resource_id=vc.get("resource_id", config.volcengine.resource_id),
            ws_url=vc.get("ws_url", config.volcengine.ws_url),
        )
    
    # Load interaction config
    if "interaction" in data:
        ic = data["interaction"]
        config.interaction = InteractionConfig(
            trigger_key=ic.get("trigger_key", config.interaction.trigger_key),
            mode=ic.get("mode", config.interaction.mode),
        )
    
    # Load audio config
    if "audio" in data:
        ac = data["audio"]
        config.audio = AudioConfig(
            device_index=ac.get("device_index"),
            sample_rate=ac.get("sample_rate", config.audio.sample_rate),
            channels=ac.get("channels", config.audio.channels),
            chunk_duration_ms=ac.get("chunk_duration_ms", config.audio.chunk_duration_ms),
        )
    
    # Load input config
    if "input" in data:
        inp = data["input"]
        config.input = InputConfig(
            typing_delay_ms=inp.get("typing_delay_ms", config.input.typing_delay_ms),
        )
    
    # Validate required fields
    if not config.volcengine.app_key:
        raise ValueError("volcengine.app_key is required")
    if not config.volcengine.access_key:
        raise ValueError("volcengine.access_key is required")
    
    return config


def ensure_config_dir() -> Path:
    """Ensure the config directory exists and return its path."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    return config_path
