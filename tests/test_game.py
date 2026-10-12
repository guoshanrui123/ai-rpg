import pytest

import app as web
import game


@pytest.fixture
def player(monkeypatch):
    web.sessions.clear()
    web.app.config.update(TESTING=True)
    # Fail loudly if an offline playthrough touches any paid service.
    monkeypatch.setattr(web, "ChatBot", lambda: pytest.fail("Offline mode invoked an AI service"))
    monkeypatch.setattr(web, "synthesize", lambda *args: pytest.fail("Offline mode invoked speech service"))
    client = web.app.test_client()
    client.get("/chatpage?card=3&mode=demo")
    return client


def submit(client, path, **data):
    with client.session_transaction() as s:
        token = s["csrf_token"]
    return client.post(path, data=data, headers={"X-CSRF-Token": token})


@pytest.mark.parametrize("ending,title", [("peace", "和平告别"), ("join", "地下的读者"), ("flee", "未解的秘密")])
def test_complete_playthrough(player, monkeypatch, ending, title):
    first = player.get("/gamestart").json
    assert first["game"]["location"] == "旧宅书房"
    assert "食尸鬼" not in first["message"]
    player.get("/gamestart")
    assert len(player.get("/get_messages").json["chat_history"]) == 1
    monkeypatch.setattr(game.secrets, "randbelow", lambda n: 0)
    submit(player, "/game_action", action="search")
    assert submit(player, "/roll").json["game"]["clues"]
    submit(player, "/game_action", action="cemetery")
    submit(player, "/game_action", action="keeper")
    assert submit(player, "/roll").json["game"]["location"] == "低矮墓碑"
    submit(player, "/game_action", action="open")
    check = player.get("/get_messages").json["game"]["pending_check"]
    assert check["threshold"] == 45  # Selected card is authoritative.
    assert submit(player, "/roll").json["game"]["location"] == "与道格拉斯交谈"
    submit(player, "/game_action", action="ask")
    result = submit(player, "/game_action", action=ending)
    assert result.status_code == 200
    assert result.json["game"]["ending"]["title"] == title
    assert title in player.get("/finalend").get_data(as_text=True)
    assert submit(player, "/game_action", action="search").status_code == 400


def test_failure_has_alternative_and_roll_is_consumed(player, monkeypatch):
    monkeypatch.setattr(game.secrets, "randbelow", lambda n: 99)
    submit(player, "/game_action", action="search")
    assert submit(player, "/game_action", action="cemetery").status_code == 400
    result = submit(player, "/roll").json
    assert "失败" in result["answer"]
    assert result["game"]["pending_check"] is None
    assert submit(player, "/roll", roll="1").status_code == 400
    assert submit(player, "/game_action", action="cemetery").status_code == 200
    monkeypatch.setattr(game.secrets, "randbelow", lambda n: 0)
    submit(player, "/game_action", action="keeper")
    submit(player, "/roll")
    monkeypatch.setattr(game.secrets, "randbelow", lambda n: 99)
    submit(player, "/game_action", action="open")
    submit(player, "/roll")
    assert submit(player, "/game_action", action="wait").json["game"]["location"] == "与道格拉斯交谈"


def test_progress_survives_refresh_and_reset_clears_it(player):
    submit(player, "/game_action", action="cemetery")
    player.get("/chatpage?card=3&mode=demo")
    assert player.get("/get_messages").json["game"]["location"] == "公墓"
    reset = submit(player, "/reset_game").json
    assert reset["game"]["location"] == "旧宅书房"
    assert not reset["game"]["clues"]
    assert len(player.get("/get_messages").json["chat_history"]) == 1


def test_invalid_actions_isolation_and_card_change(player):
    assert submit(player, "/game_action", action="peace").status_code == 400
    submit(player, "/game_action", action="cemetery")
    other = web.app.test_client()
    assert other.get("/get_messages").json["game"]["location"] == "旧宅书房"
    player.get("/chatpage?card=1&mode=demo")
    assert player.get("/get_messages").json["game"]["location"] == "旧宅书房"


def test_free_text_and_csrf(player):
    assert player.post("/roll").status_code == 403
    result = submit(player, "/send_message", message="搜索书房")
    assert result.json["game"]["pending_check"]["skill"] == "侦察"
    result = submit(player, "/send_message", message="随便问问")
    assert "先掷骰子" in result.json["answer"]
