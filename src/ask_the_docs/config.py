"""Load and validate the YAML config: tool settings and monitored codebases."""

import os
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
    """The config file is missing or invalid, or its path cannot be resolved.

    The message starts with the file path; validation errors also name the
    dotted key.
    """


def _expand_user(path: Path) -> Path:
    """Expand ``~``, raising ``ValueError`` when the home folder is unknown."""
    try:
        return path.expanduser()
    except RuntimeError as exc:
        raise ValueError("cannot expand '~': unknown user or home folder") from exc


def _normalize_root(value: str | Path) -> Path:
    """Expand ``~`` and collapse ``.`` and ``..`` without touching the disk."""
    return Path(os.path.normpath(_expand_user(Path(value))))


def _env_value(raw: str | None) -> str | None:
    """Treat an empty environment variable as unset."""
    return raw or None


class CodebaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    root: Path
    docs: list[str] = Field(default=["docs/"], min_length=1)
    exclude: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _default_name(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("name") is None:
            # A null name is absent: root fills it, or root's error is reported.
            data = {key: value for key, value in data.items() if key != "name"}
            root = data.get("root")
            if isinstance(root, (str, Path)):
                try:
                    normalized = _normalize_root(root)
                except ValueError:
                    normalized = None
                # Leave name absent for a root that will fail, so root's error shows.
                if normalized is not None and normalized.is_absolute():
                    data["name"] = normalized.name
        return data

    @field_validator("name")
    @classmethod
    def _non_empty_name(cls, name: str) -> str:
        if not name.strip():
            raise ValueError(
                "name must not be empty; set it when root has no folder name, such as '/'"
            )
        return name

    @field_validator("root")
    @classmethod
    def _absolute_root(cls, root: Path) -> Path:
        root = _normalize_root(root)
        if not root.is_absolute():
            raise ValueError("root must be an absolute path")
        return root

    @field_validator("docs")
    @classmethod
    def _relative_docs(cls, docs: list[str]) -> list[str]:
        for folder in docs:
            if not folder:
                raise ValueError("docs folder must not be empty; use '.' for the root")
            path = PurePosixPath(folder)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"docs folder {folder!r} must be relative to root")
        return docs

    @field_validator("exclude")
    @classmethod
    def _matchable_exclude(cls, exclude: list[str]) -> list[str]:
        # Discovered paths are root-relative with no empty, '.' or '..' segments,
        # so a glob with any of these, or a leading '/', can never match. A glob
        # without wildcards matches only the file at that exact path.
        for glob in exclude:
            parts = glob.split("/")
            if glob.startswith("/") or any(p in ("", ".", "..") for p in parts):
                raise ValueError(
                    f"exclude glob {glob!r} must be relative to root, such as 'docs/archive/**'"
                )
        return exclude


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codebases: list[CodebaseConfig] = Field(min_length=1)


def resolve_config_path(flag: Path | None, env: Mapping[str, str]) -> Path:
    """Return the config path: the flag, else ``ATD_CONFIG``, else the default."""
    if flag is not None:
        path = flag
    elif (env_path := _env_value(env.get(CONFIG_ENV_VAR))) is not None:
        path = Path(env_path)
    else:
        path = DEFAULT_CONFIG_PATH
    try:
        return _expand_user(path)
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc


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
    if (env_value := _env_value(env_value)) is not None:
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
    # PyYAML's constructors, such as the timestamp one, raise plain ValueError.
    except (yaml.YAMLError, ValueError) as exc:
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
