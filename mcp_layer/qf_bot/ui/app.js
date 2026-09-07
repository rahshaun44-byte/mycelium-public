
// Ultra-Premium Mobile JS Logic
function hapticFeedback(type = 'light') {
    if (navigator.vibrate) {
        if (type === 'light') navigator.vibrate(10);
        if (type === 'medium') navigator.vibrate([15, 10, 15]);
        if (type === 'heavy') navigator.vibrate([30, 20, 30, 20, 30]);
    }
}

function switchTab(tabId, btnElement) {
    hapticFeedback('light');
    document.querySelectorAll('.tab-view').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    
    document.getElementById(tabId).classList.add('active');
    btnElement.classList.add('active');
}

function sendPrompt(text) {
    document.getElementById('chatInput').value = text;
    hapticFeedback('light');
}

document.getElementById('chatForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg) return;
    
    hapticFeedback('medium');
    
    // Append user message
    const feed = document.getElementById('chatFeed');
    feed.innerHTML += `
        <div class="msg-wrapper user">
          <div class="msg-body">
            <div class="msg-content"><p>${msg}</p></div>
          </div>
        </div>
    `;
    input.value = '';
    
    // Auto-scroll
    setTimeout(() => {
        feed.scrollTop = feed.scrollHeight;
    }, 50);

    // Call REST API
    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: msg})
        });
        const data = await res.json();
        
        feed.innerHTML += `
            <div class="msg-wrapper bot">
              <div class="msg-avatar">⬡</div>
              <div class="msg-body">
                <div class="msg-content"><p>${data.response}</p></div>
              </div>
            </div>
        `;
        feed.scrollTop = feed.scrollHeight;
    } catch (e) {
        console.error("API error", e);
    }
});
