import core.kite as kite_mod
import core.settings_store as store


def _use_tmp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "settings.db"))


def test_set_access_token_persists_row(monkeypatch, tmp_path):
    _use_tmp_db(monkeypatch, tmp_path)
    monkeypatch.setattr(kite_mod.kite, "set_access_token", lambda t: None)

    kite_mod.set_access_token("tok-123")

    saved = store.load_settings("kite_session", {})
    assert saved["access_token"] == "tok-123"
    assert saved["ist_date"] == kite_mod._today_ist()


def test_load_restores_same_day_token(monkeypatch, tmp_path):
    _use_tmp_db(monkeypatch, tmp_path)
    monkeypatch.setattr(kite_mod.kite, "set_access_token", lambda t: None)
    store.save_settings("kite_session", {"access_token": "tok-abc", "ist_date": kite_mod._today_ist()})

    kite_mod._access_token = None
    kite_mod._load_persisted_token()

    assert kite_mod._access_token == "tok-abc"
    assert kite_mod.is_authenticated() is True


def test_load_ignores_stale_token(monkeypatch, tmp_path):
    _use_tmp_db(monkeypatch, tmp_path)
    monkeypatch.setattr(kite_mod.kite, "set_access_token", lambda t: None)
    store.save_settings("kite_session", {"access_token": "tok-old", "ist_date": "1999-01-01"})

    kite_mod._access_token = None
    kite_mod._load_persisted_token()

    assert kite_mod._access_token is None
