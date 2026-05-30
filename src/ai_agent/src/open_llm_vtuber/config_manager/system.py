# config_manager/system.py
from pydantic import Field, model_validator
from typing import Dict, ClassVar
from .i18n import I18nMixin, Description


class SystemConfig(I18nMixin):
    """System configuration settings."""

    conf_version: str = Field(..., alias="conf_version")
    host: str = Field(..., alias="host")
    port: int = Field(..., alias="port")
    config_alts_dir: str = Field(..., alias="config_alts_dir")
    tool_prompts: Dict[str, str] = Field(..., alias="tool_prompts")
    enable_proxy: bool = Field(False, alias="enable_proxy")
    wake_word: str = Field("", alias="wake_word")
    wake_timeout: float = Field(30.0, alias="wake_timeout")
    wake_response: str = Field("我在，有什么可以帮助您吗？", alias="wake_response")
    sleep_response: str = Field("再见", alias="sleep_response")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "conf_version": Description(en="Configuration version", zh="配置文件版本"),
        "host": Description(en="Server host address", zh="服务器主机地址"),
        "port": Description(en="Server port number", zh="服务器端口号"),
        "config_alts_dir": Description(
            en="Directory for alternative configurations", zh="备用配置目录"
        ),
        "tool_prompts": Description(
            en="Tool prompts to be inserted into persona prompt",
            zh="要插入到角色提示词中的工具提示词",
        ),
        "enable_proxy": Description(
            en="Enable proxy mode for multiple clients",
            zh="启用代理模式以支持多个客户端使用一个 ws 连接",
        ),
        "wake_word": Description(
            en="Wake word to trigger the AI (e.g., '你好小戴')",
            zh="触发 AI 的唤醒词（如 '你好小戴'）",
        ),
        "wake_timeout": Description(
            en="Seconds of inactivity before the AI goes back to sleep",
            zh="AI 进入睡眠状态前的静止时间（秒）",
        ),
        "wake_response": Description(
            en="Response when the AI is woken up",
            zh="AI 被唤醒时的回应语",
        ),
        "sleep_response": Description(
            en="Response when the AI goes back to sleep",
            zh="AI 进入睡眠状态时的回应语",
        ),
    }

    @model_validator(mode="after")
    def check_port(cls, values):
        port = values.port
        if port < 0 or port > 65535:
            raise ValueError("Port must be between 0 and 65535")
        return values
