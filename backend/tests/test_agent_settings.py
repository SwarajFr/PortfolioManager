import core.settings_store as store
import features.agent.settings as agent_settings


def test_defaults_on_empty_db(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "settings.db"))
    conf = agent_settings.get_settings()
    assert conf["model"] == "gemma4:e4b"
    assert conf["max_tool_iterations"] == 8
    assert "read-only" in conf["system_prompt"].lower()
