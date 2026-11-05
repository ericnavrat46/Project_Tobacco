document.addEventListener('DOMContentLoaded', function () {
    const toggler = document.getElementById('chatbotToggler');
    const closeBtn = document.getElementById('chatbotClose');
    const clearBtn = document.getElementById('chatbotClear');
    const form = document.getElementById('chatbotForm');
    const input = document.getElementById('chatbotInput');
    const messages = document.getElementById('chatbotMessages');
    const typing = document.getElementById('chatbotTyping');
    const suggestionsContainer = document.querySelector('.chatbot-suggestions');
    const suggestionChips = document.querySelectorAll('.suggestion-chip');

    if (!toggler || !form || !input || !messages) return;

    const STORAGE_KEY = 'tobaccoguard_chat_history_v1';
    let chatHistory = [];

    // Markdown formatting helper
    function formatMarkdown(text) {
        if (!text) return '';
        let escaped = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Headings
        escaped = escaped.replace(/^### (.*$)/gim, '<h5>$1</h5>');
        escaped = escaped.replace(/^## (.*$)/gim, '<h4>$1</h4>');
        escaped = escaped.replace(/^# (.*$)/gim, '<h3>$1</h3>');

        // Bold & Italic
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        escaped = escaped.replace(/\*(.*?)\*/g, '<em>$1</em>');

        // Horizontal rules
        escaped = escaped.replace(/^---$/gim, '<hr style="margin: 8px 0; border-color: #e2e8f0;">');

        // Bullet points
        escaped = escaped.replace(/^\s*[\-\*]\s+(.*)$/gm, '<li>$1</li>');
        escaped = escaped.replace(/(<li>.*<\/li>(\s*<li>.*<\/li>)*)/g, '<ul>$1</ul>');

        // Numbered lists
        escaped = escaped.replace(/^\s*\d+\.\s+(.*)$/gm, '<li>$1</li>');

        // Linebreaks
        escaped = escaped.replace(/\n{2,}/g, '<br><br>').replace(/\n/g, '<br>');

        return escaped;
    }

    function getCurrentTime() {
        const now = new Date();
        return now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
    }

    function scrollToBottom() {
        messages.scrollTop = messages.scrollHeight;
    }

    function appendMessage(sender, text, time, saveToStorage = true) {
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${sender}`;

        const formatted = sender === 'bot' ? formatMarkdown(text) : text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        const displayTime = time || getCurrentTime();
        bubble.innerHTML = `${formatted}<span class="chat-time">${displayTime}</span>`;

        messages.insertBefore(bubble, typing);
        scrollToBottom();

        if (saveToStorage) {
            chatHistory.push({
                role: sender === 'bot' ? 'model' : 'user',
                text: text,
                time: displayTime
            });
            // Batasi penyimpanan 20 pesan terakhir di localStorage
            if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory));
            } catch (e) {
                console.warn('localStorage chat quota exceeded');
            }
        }
    }

    // Load riwayat chat dari localStorage saat pertama kali buka
    function loadSavedHistory() {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved) {
                const parsed = JSON.parse(saved);
                if (Array.isArray(parsed) && parsed.length > 0) {
                    chatHistory = parsed;
                    parsed.forEach(item => {
                        appendMessage(item.role === 'model' ? 'bot' : 'user', item.text, item.time, false);
                    });
                }
            }
        } catch (e) {
            console.error('Failed to load chat history', e);
        }
    }

    loadSavedHistory();

    // Toggle Chat Popup (Buka / Tutup)
    function toggleChat(forceState) {
        if (typeof forceState === 'boolean') {
            document.body.classList.toggle('chatbot-open', forceState);
        } else {
            document.body.classList.toggle('chatbot-open');
        }
        if (document.body.classList.contains('chatbot-open')) {
            setTimeout(() => {
                input.focus();
                scrollToBottom();
            }, 200);
        }
    }

    toggler.addEventListener('click', () => toggleChat());

    if (clearBtn) {
        clearBtn.addEventListener('click', function() {
            if (confirm('Hapus seluruh riwayat percakapan?')) {
                localStorage.removeItem(STORAGE_KEY);
                chatHistory = [];
                // Hapus semua chat bubbles kecuali bubble default bot pertama
                const bubbles = messages.querySelectorAll('.chat-bubble');
                bubbles.forEach((b, idx) => {
                    if (idx > 0) b.remove();
                });
            }
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', () => toggleChat(false));
    }

    // Horizontal scroll support with mouse wheel on suggestion chips
    if (suggestionsContainer) {
        suggestionsContainer.addEventListener('wheel', function (e) {
            if (e.deltaY !== 0) {
                e.preventDefault();
                suggestionsContainer.scrollLeft += e.deltaY;
            }
        });

        // Mouse drag scrolling support
        let isDown = false;
        let startX, scrollLeft;
        suggestionsContainer.addEventListener('mousedown', (e) => {
            isDown = true;
            startX = e.pageX - suggestionsContainer.offsetLeft;
            scrollLeft = suggestionsContainer.scrollLeft;
        });
        suggestionsContainer.addEventListener('mouseleave', () => { isDown = false; });
        suggestionsContainer.addEventListener('mouseup', () => { isDown = false; });
        suggestionsContainer.addEventListener('mousemove', (e) => {
            if (!isDown) return;
            e.preventDefault();
            const x = e.pageX - suggestionsContainer.offsetLeft;
            const walk = (x - startX) * 1.5;
            suggestionsContainer.scrollLeft = scrollLeft - walk;
        });
    }

    function showTyping(show) {
        if (typing) {
            typing.style.display = show ? 'flex' : 'none';
            if (show) scrollToBottom();
        }
    }

    async function sendMessage(text) {
        const trimmed = text.trim();
        if (!trimmed) return;

        appendMessage('user', trimmed);
        input.value = '';
        input.disabled = true;
        showTyping(true);

        // Siapkan history untuk API backend (hanya format role & text)
        const apiHistory = chatHistory.slice(-6).map(h => ({
            role: h.role,
            text: h.text
        }));

        try {
            const resp = await fetch('/api/chatbot/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: trimmed,
                    history: apiHistory
                })
            });

            const data = await resp.json();
            showTyping(false);
            input.disabled = false;
            input.focus();

            if (data.success && data.reply) {
                appendMessage('bot', data.reply);
            } else {
                appendMessage('bot', '⚠️ ' + (data.error || 'Terjadi kesalahan saat menghubungi server AI.'));
            }
        } catch (err) {
            showTyping(false);
            input.disabled = false;
            input.focus();
            appendMessage('bot', '⚠️ Gagal terhubung ke server. Periksa koneksi internet Anda.');
        }
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        sendMessage(input.value);
    });

    // Quick suggestions click
    suggestionChips.forEach(chip => {
        chip.addEventListener('click', function () {
            const prompt = this.getAttribute('data-prompt') || this.innerText;
            sendMessage(prompt);
        });
    });
});
