import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from apflow.core.config_manager import get_config_manager


@pytest.fixture(autouse=True)
def _reset_config_manager():
    cm = get_config_manager()
    cm.clear()
    yield
    cm.clear()


def test_register_pre_post_hooks_via_config_manager():
    cm = get_config_manager()

    recorded: List[str] = []

    def pre_hook(task: Any) -> None:  # type: ignore[unused-argument]
        recorded.append("pre")

    def post_hook(task: Any, inputs: Dict[str, Any], result: Any) -> None:  # type: ignore[unused-argument]
        recorded.append("post")

    cm.register_pre_hook(pre_hook)
    cm.register_post_hook(post_hook)

    assert pre_hook in cm.get_pre_hooks()
    assert post_hook in cm.get_post_hooks()


def test_register_task_tree_hook_via_config_manager():
    cm = get_config_manager()

    def on_completed(root_task: Any, *_: Any) -> None:  # type: ignore[unused-argument]
        return

    cm.register_task_tree_hook("on_tree_completed", on_completed)

    hooks = cm.get_task_tree_hooks("on_tree_completed")
    assert on_completed in hooks


def test_demo_sleep_scale_roundtrip():
    cm = get_config_manager()
    cm.set_demo_sleep_scale(0.5)
    assert cm.get_demo_sleep_scale() == 0.5


def test_load_env_files_uses_dotenv_when_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cm = get_config_manager()

    loaded: Dict[str, Any] = {}

    def fake_load_dotenv(path: Path, override: bool = False) -> None:
        loaded["path"] = path
        loaded["override"] = override

    fake_dotenv = SimpleNamespace(load_dotenv=fake_load_dotenv)
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    env_file = tmp_path / ".env"
    env_file.write_text("KEY=value", encoding="utf-8")

    cm.load_env_files([env_file], override=False)

    assert loaded.get("path") == env_file
    assert loaded.get("override") is False
