"""窗口位置与 `.bak` 回退的存储测试。"""

import json

from orbit.storage import WindowState, load_state, save_state
from orbit.storage.config import Config, Schedule, load_config, save_config
from orbit.storage.jsonio import load_json, save_json


def test_missing_file_means_unknown_position(tmp_path):
    state = load_state(tmp_path / "window.json")
    assert state.known is False
    assert state.as_point() is None


def test_position_roundtrip(tmp_path):
    path = tmp_path / "window.json"
    save_state(WindowState(120, -40), path)  # 副屏在主屏左侧，x 是负数
    assert load_state(path).as_point() == (120, -40)


def test_position_rejects_non_integers(tmp_path):
    path = tmp_path / "window.json"
    path.write_text(json.dumps({"x": "left", "y": True}), encoding="utf-8")
    state = load_state(path)
    assert state.known is False


def test_half_position_is_not_known(tmp_path):
    path = tmp_path / "window.json"
    path.write_text(json.dumps({"x": 10}), encoding="utf-8")
    assert load_state(path).known is False


def test_config_survives_a_broken_edit_via_backup(tmp_path):
    """手改坏一个逗号，不该连作息一起丢。"""
    path = tmp_path / "config.json"
    good = Config(mode="fixed", fixed=Schedule("09:00", "23:00"))
    save_config(good, path)
    save_config(Config(mode="fixed", fixed=Schedule("08:00", "22:00")), path)

    path.write_text("{ this is not json", encoding="utf-8")
    assert (tmp_path / "config.json.bak").exists()

    restored = load_config(path)
    assert restored.fixed.wake == "09:00"
    assert restored.fixed.sleep == "23:00"


def test_save_writes_no_tmp_leftover(tmp_path):
    path = tmp_path / "config.json"
    save_config(Config(mode="fixed", fixed=Schedule("09:00", "23:00")), path)
    leftovers = [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []
    assert json.loads(path.read_text(encoding="utf-8"))["mode"] == "fixed"


def test_load_json_ignores_non_object(tmp_path):
    path = tmp_path / "x.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_json(path) is None


def test_save_json_creates_parent_directory(tmp_path):
    target = tmp_path / "deep" / "nested" / "x.json"
    save_json(target, {"a": 1})
    assert target.exists()
