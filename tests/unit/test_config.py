import re
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

    with pytest.raises(ConfigError, match=re.escape(str(path))):
        load_config(path)


def test_non_utf8_file_names_the_file(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_bytes(b"codebases:\n  - root: /caf\xe9\n")

    with pytest.raises(
        ConfigError, match=re.escape(f"{path}: config file is not valid UTF-8")
    ):
        load_config(path)


def test_invalid_yaml_names_the_file(tmp_path):
    path = write(tmp_path, "codebases: [unclosed\n")

    with pytest.raises(ConfigError, match=re.escape(f"{path}: invalid YAML")):
        load_config(path)


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("codebases:\n  - root: /a\n    colour: red\n", "codebases.0.colour"),
        ("codebases:\n  - root: /a\n    docs: 5\n", "codebases.0.docs"),
        ("codebases:\n  - root: /a\n  - root: relative/b\n", "codebases.1.root"),
        ("codebases:\n  - root: /a\nelasticsearch: {}\n", "elasticsearch"),
        ("codebases: []\n", "codebases"),
        ("codebases:\n  - root: /a\n    docs: ['']\n", "codebases.0.docs"),
        ("codebases:\n  - root: /a\n    docs: []\n", "codebases.0.docs"),
        (
            "codebases:\n  - root: /a\n    exclude: [/docs/x/**]\n",
            "codebases.0.exclude",
        ),
        (
            "codebases:\n  - root: /a\n    exclude: [./docs/x/**]\n",
            "codebases.0.exclude",
        ),
        ("codebases:\n  - root: /a\n    exclude: [docs/x/]\n", "codebases.0.exclude"),
        ("codebases:\n  - root: /a\n    exclude: ['']\n", "codebases.0.exclude"),
        ("codebases:\n  - root: 5\n", "codebases.0.root"),
        ("codebases:\n  - docs: [docs/]\n", "codebases.0.root"),
        ("codebases:\n  - root: /a\n    docs: [/abs/docs]\n", "codebases.0.docs"),
        ("codebases:\n  - root: /a\n    docs: [../shared]\n", "codebases.0.docs"),
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

    with pytest.raises(ConfigError, match=re.escape(str(path))):
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


def test_root_docs_folder_loads(tmp_path):
    path = write(tmp_path, "codebases:\n  - root: /a\n    docs: [.]\n")

    assert load_config(path).codebases[0].docs == ["."]


def test_impossible_yaml_date_is_invalid_yaml(tmp_path):
    path = write(tmp_path, "codebases:\n  - root: /a\nadded: 2024-13-45\n")

    with pytest.raises(ConfigError, match=re.escape(f"{path}: invalid YAML")):
        load_config(path)


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("codebases:\n  - root: ~nosuchuser_atd/x\n", "codebases.0.root"),
        ("codebases:\n  - name:\n", "codebases.0.root"),
        ("codebases:\n  - root: /\n", "codebases.0.name"),
        ("codebases:\n  - root: .\n", "codebases.0.root"),
        ("codebases:\n  - root: ''\n", "codebases.0.root"),
        ("codebases:\n  - root: ./x/..\n", "codebases.0.root"),
        ("codebases:\n  - name: ''\n    root: /a\n", "codebases.0.name"),
    ],
)
def test_root_and_name_errors_name_the_key(tmp_path, text, key):
    path = write(tmp_path, text)

    with pytest.raises(ConfigError) as excinfo:
        load_config(path)

    assert str(excinfo.value).startswith(f"{path}: {key}: ")


def test_root_is_normalized_before_naming(tmp_path):
    path = write(tmp_path, "codebases:\n  - root: /srv/widgets/docs/..\n")

    (codebase,) = load_config(path).codebases

    assert (codebase.name, codebase.root) == ("widgets", Path("/srv/widgets"))


def test_normalized_roots_share_a_name(tmp_path):
    path = write(tmp_path, "codebases:\n  - root: /x/a\n  - root: /y/a/b/..\n")

    with pytest.raises(ConfigError, match=re.escape(f"{path}: codebases.1.name: ")):
        load_config(path)


@pytest.mark.parametrize("flag", [Path("~nosuchuser_atd/c.yaml"), None])
def test_config_path_with_unknown_user_raises_config_error(flag):
    env = {"ATD_CONFIG": "~nosuchuser_atd/c.yaml"}

    with pytest.raises(ConfigError) as excinfo:
        resolve_config_path(flag, env)

    assert str(excinfo.value).count("nosuchuser_atd") == 1


def test_empty_env_value_counts_as_unset():
    assert (
        resolve_config_path(None, {"ATD_CONFIG": ""})
        == DEFAULT_CONFIG_PATH.expanduser()
    )
    assert resolve_setting(None, "", 10, 5, convert=int) == 10
