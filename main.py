from fastapi.responses import HTMLResponse
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.routers.v1 import notification_routes
from infras.db.mongo import MongoDBManager
from core.configs.settings_config import SETTINGS

import asyncio
from messaging.worker import worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to MongoDB
    await MongoDBManager.connect()
    # Start RabbitMQ worker
    asyncio.create_task(worker())
    yield
    # Shutdown: Close connections
    await MongoDBManager.disconnect()

app = FastAPI(
    title="Notification Service",
    description="Microservice handling WebSocket notifications and offline MongoDB fallback storage",
    lifespan=lifespan
)

app.include_router(notification_routes.router)

@app.get("/", response_class=HTMLResponse)
async def serve_test_client():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Notification Service Test Client</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-gradient: linear-gradient(135deg, #0f0c1b 0%, #15102a 50%, #06020f 100%);
                --card-bg: rgba(255, 255, 255, 0.04);
                --card-border: rgba(255, 255, 255, 0.08);
                --text-primary: #f3f1f8;
                --text-secondary: #a39eb9;
                --accent-primary: #7c4dff;
                --accent-success: #00e676;
                --accent-error: #ff1744;
                --accent-warning: #ffea00;
            }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'Outfit', sans-serif;
            }

            body {
                background: var(--bg-gradient);
                color: var(--text-primary);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 2rem;
            }

            header {
                text-align: center;
                margin-bottom: 2rem;
            }

            header h1 {
                font-size: 2.5rem;
                font-weight: 700;
                background: linear-gradient(90deg, #b388ff, #8c9eff);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 0.5rem;
            }

            header p {
                color: var(--text-secondary);
                font-size: 1rem;
            }

            .container {
                width: 100%;
                max-width: 900px;
                display: grid;
                grid-template-columns: 320px 1fr;
                gap: 2rem;
            }

            .panel {
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                backdrop-filter: blur(16px);
                border-radius: 16px;
                padding: 1.5rem;
                display: flex;
                flex-direction: column;
                gap: 1.5rem;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            }

            .form-group {
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
            }

            label {
                font-size: 0.85rem;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: var(--text-secondary);
            }

            input {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid var(--card-border);
                color: var(--text-primary);
                padding: 0.75rem 1rem;
                border-radius: 8px;
                font-size: 1rem;
                outline: none;
                transition: border-color 0.3s, background-color 0.3s;
            }

            input:focus {
                border-color: var(--accent-primary);
                background: rgba(255, 255, 255, 0.08);
            }

            button {
                background: var(--accent-primary);
                color: white;
                border: none;
                padding: 0.75rem 1rem;
                border-radius: 8px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, filter 0.2s;
            }

            button:hover {
                filter: brightness(1.1);
            }

            button:active {
                transform: scale(0.98);
            }

            .btn-outline {
                background: transparent;
                border: 1px solid var(--accent-primary);
                color: var(--accent-primary);
            }

            .status-container {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                padding: 0.75rem;
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid var(--card-border);
            }

            .status-dot {
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: var(--accent-error);
                box-shadow: 0 0 8px var(--accent-error);
                transition: background-color 0.3s, box-shadow 0.3s;
            }

            .status-dot.connected {
                background: var(--accent-success);
                box-shadow: 0 0 8px var(--accent-success);
            }

            .status-dot.connecting {
                background: var(--accent-warning);
                box-shadow: 0 0 8px var(--accent-warning);
            }

            .status-text {
                font-size: 0.9rem;
                font-weight: 500;
            }

            .notifications-area {
                display: flex;
                flex-direction: column;
                gap: 1rem;
                max-height: 550px;
                overflow-y: auto;
                padding-right: 0.5rem;
            }

            .notifications-area::-webkit-scrollbar {
                width: 6px;
            }

            .notifications-area::-webkit-scrollbar-thumb {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
            }

            .no-notifications {
                text-align: center;
                padding: 3rem;
                color: var(--text-secondary);
                border: 1px dashed var(--card-border);
                border-radius: 12px;
                font-style: italic;
            }

            .notification-card {
                background: rgba(255, 255, 255, 0.02);
                border-left: 4px solid var(--accent-primary);
                border-top: 1px solid var(--card-border);
                border-right: 1px solid var(--card-border);
                border-bottom: 1px solid var(--card-border);
                border-radius: 0 12px 12px 0;
                padding: 1.25rem;
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
                position: relative;
                animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            }

            .notification-card.error {
                border-left-color: var(--accent-error);
            }

            .notification-card.warning {
                border-left-color: var(--accent-warning);
            }

            .notification-card.announcement {
                border-left-color: #00b0ff;
            }

            .notif-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .notif-title {
                font-weight: 600;
                font-size: 1.1rem;
            }

            .notif-time {
                font-size: 0.75rem;
                color: var(--text-secondary);
            }

            .notif-message {
                color: var(--text-secondary);
                font-size: 0.95rem;
                line-height: 1.4;
            }

            .notif-tag {
                font-size: 0.7rem;
                text-transform: uppercase;
                background: rgba(255, 255, 255, 0.05);
                padding: 0.2rem 0.5rem;
                border-radius: 4px;
                letter-spacing: 0.05em;
                color: var(--text-secondary);
            }

            .notif-delete {
                position: absolute;
                top: 0.75rem;
                right: 0.75rem;
                background: transparent;
                border: none;
                color: var(--text-secondary);
                cursor: pointer;
                font-size: 0.8rem;
                padding: 0.25rem;
                border-radius: 4px;
                opacity: 0;
                transition: opacity 0.2s, color 0.2s;
            }

            .notification-card:hover .notif-delete {
                opacity: 1;
            }

            .notif-delete:hover {
                color: var(--accent-error);
                background: rgba(255, 255, 255, 0.05);
            }

            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
        </style>
    </head>
    <body>
        <header>
            <h1>Notification Service</h1>
            <p>Real-Time WebSocket & Fallback Test Client</p>
        </header>

        <div class="container">
            <div class="panel">
                <div class="form-group">
                    <label for="userId">User ID</label>
                    <input type="text" id="userId" value="user123" placeholder="Enter User ID">
                </div>

                <div class="status-container">
                    <div id="statusDot" class="status-dot"></div>
                    <span id="statusText" class="status-text">Disconnected</span>
                </div>

                <button id="connectBtn" onclick="toggleConnection()">Connect WebSocket</button>
                <button id="getFallbackBtn" class="btn-outline" onclick="fetchStoredNotifications()">Get Offline Notifications</button>
            </div>

            <div class="panel" style="flex-grow: 1;">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid var(--card-border); padding-bottom: 0.75rem;">
                    <label>Real-Time Notification Feed</label>
                    <button class="btn-outline" style="font-size: 0.8rem; padding: 0.4rem 0.8rem;" onclick="clearFeed()">Clear Feed</button>
                </div>

                <div id="notificationsArea" class="notifications-area">
                    <div class="no-notifications" id="noNotifications">
                        No notifications received. Connect via WebSocket or pull offline ones.
                    </div>
                </div>
            </div>
        </div>

        <script>
            let socket = null;

            function toggleConnection() {
                const userId = document.getElementById('userId').value.trim();
                const connectBtn = document.getElementById('connectBtn');
                const statusDot = document.getElementById('statusDot');
                const statusText = document.getElementById('statusText');

                if (!userId) {
                    alert('Please enter a User ID');
                    return;
                }

                if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
                    socket.close();
                    return;
                }

                connectBtn.innerText = 'Disconnect';
                statusDot.className = 'status-dot connecting';
                statusText.innerText = 'Connecting...';

                // Determine correct WebSocket URL
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/api/v1/notifications/ws/${userId}`;
                
                socket = new WebSocket(wsUrl);

                socket.onopen = function(e) {
                    statusDot.className = 'status-dot connected';
                    statusText.innerText = 'Connected';
                };

                socket.onmessage = function(event) {
                    try {
                        const notif = JSON.parse(event.data);
                        addNotificationCard(notif);
                    } catch (err) {
                        console.error('Error parsing notification JSON:', err);
                    }
                };

                socket.onclose = function(event) {
                    statusDot.className = 'status-dot';
                    statusText.innerText = 'Disconnected';
                    connectBtn.innerText = 'Connect WebSocket';
                    socket = null;
                };

                socket.onerror = function(error) {
                    console.error('WebSocket Error:', error);
                };
            }

            async function fetchStoredNotifications() {
                const userId = document.getElementById('userId').value.trim();
                if (!userId) {
                    alert('Please enter a User ID');
                    return;
                }

                try {
                    const response = await fetch(`/api/v1/notifications/?user_id=${userId}`);
                    if (!response.ok) throw new Error('Failed to fetch fallback notifications');
                    const data = await response.json();
                    
                    if (data.length === 0) {
                        alert('No offline/stored notifications found for this user.');
                        return;
                    }

                    data.forEach(notif => {
                        addNotificationCard(notif);
                    });
                } catch (err) {
                    alert('Error: ' + err.message);
                }
            }

            async function deleteStoredNotification(notifId, cardElement) {
                try {
                    const response = await fetch(`/api/v1/notifications/${notifId}`, {
                        method: 'DELETE'
                    });
                    if (response.ok) {
                        cardElement.remove();
                        checkEmptyFeed();
                    } else {
                        alert('Failed to delete notification');
                    }
                } catch (err) {
                    alert('Error: ' + err.message);
                }
            }

            function addNotificationCard(notif) {
                const area = document.getElementById('notificationsArea');
                const noNotif = document.getElementById('noNotifications');
                if (noNotif) noNotif.style.display = 'none';

                const card = document.createElement('div');
                card.className = `notification-card ${notif.type || 'info'}`;

                // Formatted Time
                const dateStr = notif.created_at ? new Date(notif.created_at).toLocaleTimeString() : new Date().toLocaleTimeString();

                card.innerHTML = `
                    <div class="notif-header">
                        <span class="notif-title">${notif.title}</span>
                        <div style="display:flex; align-items:center; gap:0.5rem;">
                            <span class="notif-tag">${notif.type}</span>
                            <span class="notif-time">${dateStr}</span>
                        </div>
                    </div>
                    <div class="notif-message">${notif.message}</div>
                `;

                // If it has a database ID, show a delete button
                if (notif.id) {
                    const deleteBtn = document.createElement('button');
                    deleteBtn.className = 'notif-delete';
                    deleteBtn.innerText = 'Delete';
                    deleteBtn.onclick = function() {
                        deleteStoredNotification(notif.id, card);
                    };
                    card.appendChild(deleteBtn);
                }

                area.insertBefore(card, area.firstChild);
            }

            function clearFeed() {
                const area = document.getElementById('notificationsArea');
                area.innerHTML = `
                    <div class="no-notifications" id="noNotifications">
                        No notifications received. Connect via WebSocket or pull offline ones.
                    </div>
                `;
            }

            function checkEmptyFeed() {
                const area = document.getElementById('notificationsArea');
                if (area.children.length <= 1) { // includes noNotifications element
                    clearFeed();
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=SETTINGS.PORT, reload=True)
