from pathlib import Path

import pytest

from ask_the_docs.config import (
    DEFAULT_CONFIG_PATH,
    CodebaseConfig,
    ConfigError,
    load_config,
    resolve_config_path,
    resolve_setting,
)


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text)
    return path


def test_config_path_flag_beats_env():
    path = resolve_config_path(Path("/a.yaml"), {"ATD_CONFIG": "/b.yaml"})

    assert path == Path("/a.yaml")


def test_config_path_env_beats_default():
    assert resolve_config_path(None, {"ATD_CONFIG": "/b.yaml"}) == Path("/b.yaml")


def test_config_path_default():
    path = resolve_config_path(None, {})

    assert path == DEFAULT_CONFIG_PATH.expanduser()
    assert path == Path.home() / ".config" / "ask-the-docs" / "config.yaml"


def test_setting_precedence():
    assert resolve_setting("flag", "env", "file", "default") == "flag"
    assert resolve_setting(None, "env", "file", "default") == "env"
    assert resolve_setting(None, None, "file", "default") == "file"
    assert resolve_setting(None, None, None, "default") == "default"


def test_setting_converts_env_value():
    assert resolve_setting(None, "25", 10, 5, convert=int) == 25
    assert resolve_setting(None, None, 10, 5, convert=int) == 10


def test_valid_file_applies_defaults(tmp_path):
    path = write(
        tmp_path,
        "codebases:\n"
        "  - root: ~/projects/widgets\n"
        "  - name: billing\n"
        "    root: /srv/billing\n"
        "    docs: [docs/, adr/]\n"
        '    exclude: ["docs/archive/**"]\n',
    )

    config = load_config(path)

    widgets, billing = config.codebases
    assert widgets == CodebaseConfig(
        name="widgets",
        root=Path.home() / "projects" / "widgets",
        docs=["docs/"],
        exclude=[],
    )
    assert billing.name == "billing"
    assert billing.root == Path("/srv/billing")
    assert billing.docs == ["docs/", "adr/"]
    assert billing.exclude == ["docs/archive/**"]


def test_missing_file_names_the_file(tmp_path):
    path = tmp_path / "absent.yaml"

    with pytest.raises(ConfigError, match=str(path)):
        load_config(path)


def test_invalid_yaml_names_the_file(tmp_path):
    path = write(tmp_path, "codebases: [unclosed\n")

    with pytest.raises(ConfigError, match=f"{path}: invalid YAML"):
        load_config(path)


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("codebases:\n  - root: /a\n    colour: red\n", "codebases.0.colour"),
        ("codebases:\n  - root: /a\n    docs: 5\n", "codebases.0.docs"),
        ("codebases:\n  - root: /a\n  - root: relative/b\n", "codebases.1.root"),
        ("codebases:\n  - root: /a\nelasticsearch: {}\n", "elasticsearch"),
        ("codebases: []\n", "codebases"),
        ("", "codebases"),
    ],
)
def test_validation_errors_name_file_and_key(tmp_path, text, key):
    path = write(tmp_path, text)

    with pytest.raises(ConfigError) as excinfo:
        load_config(path)

    assert str(excinfo.value).startswith(f"{path}: {key}: ")


def test_non_mapping_file_names_the_file(tmp_path):
    path = write(tmp_path, "- just\n- a list\n")

    with pytest.raises(ConfigError, match=str(path)):
        load_config(path)


def test_duplicate_name_names_second_entry(tmp_path):
    path = write(
        tmp_path,
        "codebases:\n  - root: /x/widgets\n  - name: other\n    root: /y\n"
        "  - root: /z/widgets\n",
    )

    with pytest.raises(ConfigError) as excinfo:
        load_config(path)

    assert str(excinfo.value).startswith(f"{path}: codebases.2.name: ")
    assert "widgets" in str(excinfo.value)
