"""Exercise the real LangGraph/Chroma integration without network requests."""

import shutil
from pathlib import Path
from unittest.mock import Mock

import langchain_openai
from langchain_core.messages import AIMessage

import app as web


def test_real_graph_retrieval_and_history(monkeypatch, tmp_path):
    story = Path(web.__file__).parent / "document" / "AI_RPG_Story 2.docx"
    (tmp_path / "document").mkdir()
    shutil.copyfile(story, tmp_path / "document" / story.name)
    monkeypatch.setattr(web, "ROOT", tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-placeholder")
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "False")
    fake_model = Mock(invoke=Mock(return_value=AIMessage(content="继续调查旧居。")))
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", lambda **kwargs: fake_model)
    monkeypatch.setattr(
        langchain_openai, "OpenAIEmbeddings", Mock(side_effect=AssertionError("No remote embedding service allowed"))
    )
    bot = web.ChatBot()
    history = [{"role": "user", "content": "我是谁"}, {"role": "ai", "content": "你是一位调查员。"}]
    result = bot.stream("我想调查道格拉斯", history)
    assert result == "继续调查旧居。"
    assert len(history) == 2  # Graph must not mutate another session's history.
    sent = fake_model.invoke.call_args.args[0]
    assert sent[1].content.startswith("剧情资料：\n")
    assert len(sent[1].content) > len("剧情资料：\n")
    assert sent[-1].content == "我想调查道格拉斯"
    assert [item.type for item in sent] == ["system", "system", "system", "human", "ai", "human"]
    # Reopening the index must not duplicate the same story chunks.
    count = len(bot.db.get(include=[])["ids"])
    second = web.ChatBot()
    assert len(second.db.get(include=[])["ids"]) == count > 0
