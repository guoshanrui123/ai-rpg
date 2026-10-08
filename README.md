# AI TRPG 跑团演示

基于 Flask、LangGraph 和 Chroma 的中文 AI 跑团项目。使用通义千问生成剧情，OpenAI Embeddings 检索故事资料，可选讯飞语音合成。保留人物卡、剧情背景、聊天和浏览器语音输入界面。

## 本地运行

需要 Python 3.11～3.13。推荐使用独立虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# 编辑 .env，填写自己新申请的服务凭据
.\.venv\Scripts\python.exe app.py
```

打开 http://127.0.0.1:5000 。浏览页面不需要密钥；首次发送消息时需要 `OPENAI_API_KEY` 与 `DASHSCOPE_API_KEY`，并建立本地故事索引。嵌入和聊天请求会产生相应服务费用。首次索引可能需要等待。

填写 `XFYUN_APP_ID`、`XFYUN_API_KEY`、`XFYUN_API_SECRET` 可启用语音合成；不填或语音失败时仍能收到文字回复。浏览器语音识别依赖浏览器和其语音服务，可始终通过文字输入交流。

## 数据与安全

- 凭据只从环境变量或本地 `.env` 读取，仓库不包含真实密钥，也不自动导入旧 `api_keys.json`。
- `.env`、本地 Chroma 数据库、生成音频、缓存及虚拟环境已加入忽略规则。
- 不同浏览器会话分别保存聊天记录与音频；音频需原会话才能访问。消息处理使用单进程串行锁，适合本地演示。
- 聊天记录保存在内存，最多保留 100 个会话，每个会话最多 100 条消息，一小时无操作后失效。重启后清空；模型上下文保留最近 10 条消息。
- 生成音频保存在 `runtime/audio/`，同会话再次生成时清理一小时前的音频；过期会话的目录需自行定期清理。
- 默认仅监听本机，关闭调试，校验 TLS 证书，限制请求体与输入长度，并验证 CSRF 令牌。
- 此版本适用于本地研究演示。公开网站部署还需要登录、限流、持久会话存储、生产服务器及 HTTPS；不要直接把开发服务器暴露到公网。
- ChromaDB 有已知服务端安全通告，本项目只使用进程内的本地数据库。通告、适用性判断和验证限制详见 [审查记录](REVIEW.md)，不得把 Chroma 服务端直接公开部署。
- 剧情文档保留故事正文，已清空 Office 的作者、编辑者等个人属性；图片与剧情素材的使用授权由项目持有者确认。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

回归测试模拟外部服务，不需要真实密钥、不消耗 API 额度。覆盖页面路由、会话隔离、CSRF、输入限制、检定边界、音频访问权限、语音失败降级、PCM 转 WAV 和语音流结束帧处理。实际外部服务的连通性与额度需要配置有效凭据后另行验证。
