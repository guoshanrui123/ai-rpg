from unittest.mock import Mock

import pytest

import app as web
import game
from retrieval import StoryEmbeddings


@pytest.fixture
def player(monkeypatch):
    web.sessions.clear()
    web.app.config.update(TESTING=True)
    monkeypatch.setattr(web, "chatbot", Mock(stream=Mock(return_value="托马斯请你寻找失窃藏书。")))
    monkeypatch.setattr(web, "synthesize", Mock(side_effect=AssertionError("Speech disabled by default")))
    monkeypatch.delenv("ENABLE_TTS", raising=False)
    client = web.app.test_client()
    client.get("/chatpage?card=3&mode=ai")
    return client


def post(client, message):
    with client.session_transaction() as s:
        token = s["csrf_token"]
    return client.post("/send_message", data={"message": message}, headers={"X-CSRF-Token": token})


def test_ai_text_action_creates_real_check(player, monkeypatch):
    result = post(player, "我想搜索书房")
    assert result.status_code == 200
    assert result.json["game"]["pending_check"]["skill"] == "侦察"
    web.chatbot.stream.assert_not_called()
    assert "先掷骰子" in post(player, "继续聊聊").json["answer"]
    web.chatbot.stream.assert_not_called()


def test_question_does_not_move_player(player):
    result = post(player, "叔叔为什么去墓地？")
    assert result.json["game"]["location"] == "旧宅书房"
    assert result.json["game"]["pending_check"] is None
    web.chatbot.stream.assert_called_once()


def test_negated_plan_does_not_trigger_move(player):
    result = post(player, "不要去墓地，我想去图书馆")
    assert result.json["game"]["location"] == "镇立图书馆"


def test_actions_work_with_broken_credentials(player, monkeypatch):
    monkeypatch.setattr(web, "chatbot", None)
    monkeypatch.setattr(web, "ChatBot", Mock(side_effect=AssertionError("Action should not need a model")))
    assert post(player, "前往公墓").json["game"]["location"] == "公墓"


@pytest.mark.parametrize("status,expected", [(401, "密钥无效"), (429, "额度不足")])
def test_error_keeps_state_and_redacts_details(player, status, expected):
    error = RuntimeError("sensitive-service-value")
    error.status_code = status
    web.chatbot.stream.side_effect = error
    result = post(player, "你好")
    assert result.status_code == 502
    assert expected in result.json["message"]
    assert "sensitive-service-value" not in result.get_data(as_text=True)
    assert player.get("/get_messages").json["chat_history"] == []


@pytest.mark.parametrize("text", ["道格拉斯的藏书", "Hello books", "", "？？？"])
def test_local_vectors_are_stable_and_finite(text):
    embeddings = StoryEmbeddings()
    vector = embeddings.embed_query(text)
    assert vector == StoryEmbeddings().embed_documents([text])[0]
    assert len(vector) == 512
    norm = sum(value * value for value in vector)
    assert norm == 0 or norm == pytest.approx(1)


def test_ending_question_is_not_an_ending():
    state = game.new_game()
    state["scene"] = "meeting"
    assert game.interpret(state, "如果我加入地下，会发生什么？") is None
    assert game.interpret(state, "我不想加入地下") is None
    assert game.interpret(state, "我决定加入地下") == "join"
