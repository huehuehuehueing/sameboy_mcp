"""Agent configuration and LLM provider settings."""

from dataclasses import dataclass, field


# LLM Provider presets
PROVIDERS = {
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2",
        "api_key": "ollama",  # Ollama doesn't need a real key
        "supports_vision": False,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "supports_vision": False,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
        "supports_vision": False,
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1",
        "supports_vision": True,
    },
    "anthropic": {
        "base_url": None,  # Uses default Anthropic endpoint
        "default_model": "claude-sonnet-4-20250514",
        "supports_vision": True,
    },
    # vllm-mlx: local Apple Silicon vision model server
    # Start with: vllm-mlx serve mlx-community/Qwen3-VL-4B-Instruct-3bit --port 8000
    "vllm-mlx": {
        "base_url": "http://localhost:8000/v1",
        "default_model": "default",
        "api_key": "not-needed",
        "supports_vision": True,
    },
}


@dataclass
class AgentConfig:
    """Configuration for the Pokemon agent."""

    # LLM settings
    provider: str = "ollama"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None

    # Vision model (separate from text LLM, uses vllm-mlx)
    vision_provider: str | None = None  # None = same as provider
    vision_model: str | None = None
    vision_base_url: str | None = None
    vision_api_key: str | None = None

    # Emulator connection
    server_url: str | None = None  # SSE URL for existing MCP server
    lib_path: str | None = None
    rom_path: str | None = None
    gb_model: str = "CGB_E"

    # Agent behavior
    turbo: bool = False            # Run emulator in turbo mode
    display: bool = True           # Show live display
    display_scale: int = 2
    max_steps: int = 0             # 0 = unlimited
    cycle_frames: int = 30         # Frames to run between decisions (~0.5 sec)
    max_history: int = 60          # Summarize LLM history after this many messages

    # Saved state
    state_path: str | None = None       # Load state from this file on startup
    save_state_path: str | None = None  # Save state to this file on exit

    # Caching
    cache_dir: str = ".pokemon_agent_cache"
    cache_enabled: bool = True

    # Logging
    verbose: bool = False
    log_state: bool = False        # Log game state each cycle
    screenshot_on_decision: bool = True  # Capture screenshot when calling LLM

    def get_llm_config(self) -> dict:
        """Get resolved LLM configuration for text decisions."""
        preset = PROVIDERS.get(self.provider, {})
        return {
            "base_url": self.base_url or preset.get("base_url"),
            "model": self.model or preset.get("default_model", "llama3.2"),
            "api_key": self.api_key or preset.get("api_key"),
        }

    def get_vision_config(self) -> dict:
        """Get resolved config for vision model (screenshot analysis)."""
        vp = self.vision_provider or self.provider
        preset = PROVIDERS.get(vp, {})
        return {
            "base_url": self.vision_base_url or preset.get("base_url"),
            "model": self.vision_model or preset.get("default_model", "default"),
            "api_key": self.vision_api_key or preset.get("api_key"),
            "supports_vision": preset.get("supports_vision", False),
        }

    @property
    def has_vision(self) -> bool:
        """Check if vision model is available."""
        vp = self.vision_provider or self.provider
        preset = PROVIDERS.get(vp, {})
        return preset.get("supports_vision", False)
