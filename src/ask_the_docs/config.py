"""Load and validate the YAML config: tool settings and monitored codebases."""

from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

DEFAULT_CONFIG_PATH = Path("~/.config/ask-the-docs/config.yaml")
CONFIG_ENV_VAR = "ATD_CONFIG"


class ConfigError(Exception):
    """The config file is missing or invalid. The message names the file and key."""


class CodebaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    root: Path
    docs: list[str] = ["docs/"]
    exclude: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _default_name(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("name") is None and "root" in data:
            root = data["root"]
            if isinstance(root, (str, Path)):
                data = {**data, "name": Path(root).expanduser().name}
        return data

    @field_validator("root")
    @classmethod
    def _absolute_root(cls, root: Path) -> Path:
        root = root.expanduser()
        if not root.is_absolute():
            raise ValueError("root must be an absolute path")
        return root

    @field_validator("docs")
    @classmethod
    def _relative_docs(cls, docs: list[str]) -> list[str]:
        for folder in docs:
            path = PurePosixPath(folder)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"docs folder {folder!r} must be relative to root")
        return docs


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codebases: list[CodebaseConfig] = Field(min_length=1)


def resolve_config_path(flag: Path | None, env: Mapping[str, str]) -> Path:
    """Return the config path: the flag, else ``ATD_CONFIG``, else the default."""
    if flag is not None:
        return flag.expanduser()
    if env_path := env.get(CONFIG_ENV_VAR):
        return Path(env_path).expanduser()
    return DEFAULT_CONFIG_PATH.expanduser()


def resolve_setting[T](
    flag: T | None,
    env_value: str | None,
    file_value: T | None,
    default: T,
    convert: Callable[[str], T] = str,
) -> T:
    """Apply R-config-precedence: flag, then environment, then file, then default."""
    if flag is not None:
        return flag
    if env_value is not None:
        return convert(env_value)
    if file_value is not None:
        return file_value
    return default


def load_config(path: Path) -> Config:
    """Read and validate the config file at ``path``, raising ``ConfigError``."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(
            f"{path}: cannot read config file: {exc.strerror or exc}"
        ) from exc
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{path}: config file is not valid UTF-8") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc

    try:
        config = Config.model_validate(data if data is not None else {})
    except ValidationError as exc:
        errors = exc.errors()
        # A name is only missing because root could not fill it, so report root.
        error = next(
            (
                e
                for e in errors
                if not (e["type"] == "missing" and e["loc"][-1] == "name")
            ),
            errors[0],
        )
        key = ".".join(str(part) for part in error["loc"]) or "(top level)"
        raise ConfigError(f"{path}: {key}: {error['msg']}") from exc

    seen: set[str] = set()
    for index, codebase in enumerate(config.codebases):
        if codebase.name in seen:
            raise ConfigError(
                f"{path}: codebases.{index}.name: duplicate codebase name {codebase.name!r}"
            )
        seen.add(codebase.name)
    return config
