<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quiz Game Lobby</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0f172a;
            --container-bg: #1e293b;
            --card-bg: #334155;
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --secondary: #ec4899;
            --secondary-hover: #db2777;
            --danger: #ef4444;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border: #475569;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Outfit', sans-serif;
        }

        body {
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at top right, #1e1b4b, #0f172a);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            padding: 20px;
        }

        .lobby-container {
            background-color: var(--container-bg);
            width: 100%;
            max-width: 1000px;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
            display: flex;
            flex-direction: column;
            gap: 25px;
        }

        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border);
            padding-bottom: 20px;
        }

        .header h1 {
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }

        .player-count {
            background-color: var(--primary);
            padding: 8px 16px;
            border-radius: 30px;
            font-weight: 600;
            font-size: 14px;
        }

        /* Controls */
        .controls {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            background: rgba(0,0,0,0.15);
            padding: 20px;
            border-radius: 12px;
        }

        .input-group {
            display: flex;
            flex-grow: 1;
            gap: 10px;
        }

        input[type="text"] {
            flex-grow: 1;
            padding: 12px 15px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background-color: var(--bg-color);
            color: var(--text-main);
            font-size: 16px;
            outline: none;
            transition: border-color 0.2s;
        }

        input[type="text"]:focus {
            border-color: var(--primary);
        }

        button {
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 15px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        button:active {
            transform: scale(0.97);
        }

        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        .btn-add { background-color: var(--primary); color: white; }
        .btn-add:hover:not(:disabled) { background-color: var(--primary-hover); }

        .btn-random { background-color: var(--secondary); color: white; }
        .btn-random:hover:not(:disabled) { background-color: var(--secondary-hover); }

        /* Grid */
        .grid-header {
            font-size: 18px;
            color: var(--text-muted);
            margin-bottom: 10px;
        }

        .player-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 15px;
            min-height: 200px;
            align-content: start;
        }

        .empty-state {
            grid-column: 1 / -1;
            text-align: center;
            padding: 40px;
            color: var(--text-muted);
            background: rgba(255,255,255,0.02);
            border-radius: 12px;
            border: 1px dashed var(--border);
        }

        /* Player Card */
        .player-card {
            background-color: var(--card-bg);
            border-radius: 10px;
            padding: 12px 15px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            animation: popIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            border: 1px solid rgba(255,255,255,0.05);
            transition: transform 0.2s;
        }

        .player-card:hover {
            transform: translateY(-2px);
            background-color: #3f4f66;
        }

        .player-info {
            display: flex;
            align-items: center;
            gap: 10px;
            overflow: hidden;
        }

        .avatar {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 12px;
            color: white;
            flex-shrink: 0;
        }

        .player-name {
            font-weight: 600;
            font-size: 15px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .btn-remove {
            background: transparent;
            color: var(--text-muted);
            padding: 5px;
            border-radius: 5px;
            font-size: 18px;
            line-height: 1;
        }

        .btn-remove:hover {
            background-color: rgba(239, 68, 68, 0.2);
            color: var(--danger);
        }

        /* Footer */
        .footer {
            margin-top: auto;
            display: flex;
            justify-content: flex-end;
            border-top: 2px solid var(--border);
            padding-top: 20px;
        }

        .btn-start {
            background-color: #10b981;
            color: white;
            font-size: 18px;
            padding: 15px 30px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
        }

        .btn-start:hover:not(:disabled) { background-color: #059669; }

        @keyframes popIn {
            0% { opacity: 0; transform: scale(0.8); }
            100% { opacity: 1; transform: scale(1); }
        }

        /* Responsiveness */
        @media (max-width: 600px) {
            .input-group { flex-direction: column; }
            .controls { flex-direction: column; }
            .player-grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
        }
    </style>
</head>
<body>

<div class="lobby-container">
    <div class="header">
        <h1>🎮 Quiz Lobby</h1>
        <div class="player-count">
            <span id="count-display">0</span> / 30 Players
        </div>
    </div>

    <div class="controls">
        <div class="input-group">
            <input type="text" id="player-input" placeholder="Enter player name..." maxlength="20" autocomplete="off">
            <button class="btn-add" id="btn-add">Add Player</button>
        </div>
        <button class="btn-random" id="btn-random">🎲 Random Name</button>
    </div>

    <div>
        <div class="grid-header">Participants Waiting</div>
        <div class="player-grid" id="player-grid">
            <div class="empty-state">No players joined yet. Add some players to begin!</div>
        </div>
    </div>

    <div class="footer">
        <button class="btn-start" id="btn-start" disabled>Start Game 🚀</button>
    </div>
</div>

<script>
    const MAX_PLAYERS = 30;
    let players = [];

    // Pre-defined random fun names
    const randomNames = [
        "Clever Fox", "Trivia Titan", "Brainy Badger", "Quiz Whiz", 
        "Smarty Pants", "Fact Ninja", "Curious Cat", "Knowledge King", 
        "Logic Lord", "Speedy Sloth", "Mystery Maven", "Data Dragon",
        "Neon Knight", "Pixel Pirate", "Cyber Champ", "Quantum Quack"
    ];

    // Pre-defined vibrant colors for avatars
    const avatarColors = ['#f43f5e', '#8b5cf6', '#0ea5e9', '#10b981', '#f59e0b', '#ec4899', '#6366f1'];

    // DOM Elements
    const inputField = document.getElementById('player-input');
    const btnAdd = document.getElementById('btn-add');
    const btnRandom = document.getElementById('btn-random');
    const btnStart = document.getElementById('btn-start');
    const playerGrid = document.getElementById('player-grid');
    const countDisplay = document.getElementById('count-display');

    // Add custom player
    btnAdd.addEventListener('click', () => {
        const name = inputField.value.trim();
        if (name) {
            addPlayer(name);
            inputField.value = '';
            inputField.focus();
        }
    });

    // Enter key support for input
    inputField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            btnAdd.click();
        }
    });

    // Add random player
    btnRandom.addEventListener('click', () => {
        const randomName = randomNames[Math.floor(Math.random() * randomNames.length)];
        // Add a random number to avoid exact duplicates visually
        const uniqueName = `${randomName} ${Math.floor(Math.random() * 99) + 1}`;
        addPlayer(uniqueName);
    });

    function addPlayer(name) {
        if (players.length >= MAX_PLAYERS) {
            alert('Lobby is full! Maximum 30 players allowed.');
            return;
        }

        const newPlayer = {
            id: Date.now().toString() + Math.random().toString(36).substr(2, 5),
            name: name,
            color: avatarColors[Math.floor(Math.random() * avatarColors.length)]
        };

        players.push(newPlayer);
        renderLobby();
    }

    function removePlayer(id) {
        players = players.filter(p => p.id !== id);
        renderLobby();
    }

    function renderLobby() {
        // Update Count
        countDisplay.textContent = players.length;

        // Toggle button states based on limit
        const isFull = players.length >= MAX_PLAYERS;
        btnAdd.disabled = isFull;
        btnRandom.disabled = isFull;
        inputField.disabled = isFull;

        // Toggle Start button (require at least 2 players to start a multiplayer game)
        btnStart.disabled = players.length < 2;
        if(players.length < 2) {
            btnStart.textContent = "Waiting for players...";
        } else {
            btnStart.textContent = "Start Game 🚀";
        }

        // Render Grid
        playerGrid.innerHTML = ''; // Clear current grid

        if (players.length === 0) {
            playerGrid.innerHTML = '<div class="empty-state">No players joined yet. Add some players to begin!</div>';
            return;
        }

        players.forEach(player => {
            const card = document.createElement('div');
            card.className = 'player-card';
            
            // Generate initials for avatar
            const initials = player.name.substring(0, 2).toUpperCase();

            card.innerHTML = `
                <div class="player-info">
                    <div class="avatar" style="background-color: ${player.color}">${initials}</div>
                    <span class="player-name" title="${player.name}">${player.name}</span>
                </div>
                <button class="btn-remove" onclick="removePlayer('${player.id}')" title="Remove Player">×</button>
            `;
            
            playerGrid.appendChild(card);
        });
    }

    // Initial render
    renderLobby();
</script>

</body>
</html>
