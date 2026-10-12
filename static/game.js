let sending = false;
const question = document.getElementById('question');
const sendButton = document.getElementById('send-button');
const diceButton = document.getElementById('dice-button');
const voiceButton = document.getElementById('voice-button');
const resetButton = document.getElementById('reset-button');
const feedback = document.getElementById('game-feedback');
const actionBox = document.getElementById('game-actions');
const overlay = document.getElementById('waiting-for-dice');
let state = null;

function displayMessage(type, message) {
    const container = document.createElement('div');
    container.className = 'message-container message ' + type;
    const text = document.createElement('div');
    text.className = 'message-text';
    text.textContent = message;
    container.appendChild(text);
    const logs = document.getElementById('chat-logs');
    logs.appendChild(container);
    logs.scrollTop = logs.scrollHeight;
}

function updateGame(next) {
    state = next;
    document.getElementById('game-location').textContent = '当前场景：' + next.location;
    actionBox.replaceChildren();
    next.actions.forEach(action => {
        const button = document.createElement('button');
        button.textContent = action.label;
        button.addEventListener('click', () => submit('/game_action', {action: action.id}, action.label));
        actionBox.appendChild(button);
    });
    const clues = document.getElementById('game-clues');
    clues.replaceChildren();
    next.clues.forEach(clue => {
        const item = document.createElement('li');
        item.textContent = clue;
        clues.appendChild(item);
    });
    feedback.textContent = next.pending_check ? `${next.pending_check.skill}检定等待掷骰子（目标值 ${next.pending_check.threshold}）` : next.ending ? `结局：${next.ending.title}` : '选择行动继续调查。';
    document.getElementById('ending-link').hidden = !next.ending;
    diceButton.disabled = sending || !next.pending_check;
    sendButton.disabled = sending || Boolean(next.ending);
}

async function submit(path, payload, label) {
    if (sending) return;
    sending = true;
    sendButton.disabled = diceButton.disabled = resetButton.disabled = true;
    actionBox.querySelectorAll('button').forEach(button => {button.disabled = true;});
    feedback.textContent = '正在处理行动…';
    try {
        const response = await fetch(path, {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRF-Token': document.querySelector('meta[name=csrf-token]').content},
            body: new URLSearchParams(payload),
        });
        const data = await response.json();
        if (!response.ok || data.status !== 'success') throw new Error(data.message || '行动未完成，请重试。');
        if (path === '/reset_game') document.getElementById('chat-logs').replaceChildren();
        else if (label) displayMessage('user', label);
        displayMessage('ai', data.answer);
        if (path === '/send_message') question.value = '';
        if (data.game) updateGame(data.game);
        if (path === '/roll') {
            document.getElementById('waiting-text').textContent = data.answer;
            overlay.style.display = 'block';
        }
        if (data.audio_url) {
            const audio = document.getElementById('tts-audio');
            audio.hidden = false;
            document.getElementById('tts-audio-source').src = data.audio_url;
            audio.load();
            audio.play().catch(() => { feedback.textContent = '可点击播放器播放语音。'; });
        }
    } catch (error) {
        displayMessage('error', error.message);
        feedback.textContent = error.message;
    } finally {
        sending = false;
        resetButton.disabled = false;
        if (state) {
            // Restore controls without erasing the server error feedback.
            diceButton.disabled = !state.pending_check;
            sendButton.disabled = Boolean(state.ending);
            actionBox.querySelectorAll('button').forEach(button => {button.disabled = false;});
        } else sendButton.disabled = false;
    }
}

function sendMessage() {
    const message = question.value.trim();
    if (message) submit('/send_message', {message}, message);
}
question.addEventListener('keydown', event => {if (event.key === 'Enter') sendMessage();});
diceButton.addEventListener('click', () => submit('/roll', {}, '掷骰子'));
resetButton.addEventListener('click', () => submit('/reset_game', {}));
overlay.addEventListener('click', () => {overlay.style.display = 'none';});

async function loadGame() {
    try {
        let response = await fetch('/get_messages');
        if (!response.ok) throw new Error('加载游戏失败，请刷新页面。');
        let data = await response.json();
        if (!data.chat_history.length) {
            response = await fetch('/gamestart');
            if (!response.ok) throw new Error('开场加载失败，请刷新页面。');
            data = await response.json();
            displayMessage('ai', data.message);
        } else data.chat_history.forEach(item => displayMessage(item.role, item.content));
        updateGame(data.game);
    } catch (error) {feedback.textContent = error.message;}
}
loadGame();

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (Recognition) {
    const recognition = new Recognition();
    recognition.lang = 'zh-CN';
    recognition.interimResults = false;
    recognition.onresult = event => {question.value = event.results[0][0].transcript; sendMessage();};
    recognition.onend = () => {voiceButton.disabled = false; document.getElementById('voice-button-text').textContent = '语音';};
    recognition.onerror = () => {feedback.textContent = '语音识别失败，可使用文字输入。';};
    voiceButton.addEventListener('click', () => {
        if (sending) return;
        try {recognition.start(); voiceButton.disabled = true; document.getElementById('voice-button-text').textContent = '聆听中…';}
        catch {feedback.textContent = '暂时无法启动语音识别，请使用文字输入。';}
    });
} else {voiceButton.disabled = true; voiceButton.title = '此浏览器不支持语音识别，请使用文字输入。';}
