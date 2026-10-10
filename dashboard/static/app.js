// VigilAI Telemetry Dashboard Client Logic

let authToken = document.body.getAttribute('data-token') || '';
let isMuted = false;
let socket = null;

// Prompt user for token if absent in URL
if (!authToken) {
  const urlParams = new URLSearchParams(window.location.search);
  authToken = urlParams.get('token') || prompt('Enter VigilAI Dashboard Access Token:');
  if (authToken) {
    history.replaceState(null, '', `?token=${encodeURIComponent(authToken)}`);
  }
}

// Fetch telemetry status
async function fetchStatus() {
  if (!authToken) return;
  try {
    const res = await fetch(`/api/status?token=${encodeURIComponent(authToken)}`);
    if (!res.ok) {
      if (res.status === 401) {
        document.getElementById('ws-status-text').textContent = 'Unauthorized (Check Token)';
      }
      return;
    }
    const data = await res.json();
    updateUI(data);
  } catch (err) {
    console.error('Failed fetching status:', err);
  }
}

function updateUI(data) {
  // Update servo angle gauge
  if (data.servo_angle !== undefined) {
    const angle = Number(data.servo_angle);
    document.getElementById('val-servo-angle').textContent = `${angle.toFixed(1)}°`;
    // Rotate needle: 90 deg is 0 rotation, 10 deg is -80 deg, 170 deg is +80 deg
    const rotation = angle - 90;
    const needle = document.getElementById('servo-needle');
    if (needle) {
      needle.style.transform = `rotate(${rotation}deg)`;
    }
  }

  if (data.servo_state) {
    document.getElementById('val-servo-state').textContent = data.servo_state.toUpperCase();
  }

  // Update mute state
  if (data.is_muted !== undefined) {
    isMuted = data.is_muted;
    const muteVal = document.getElementById('val-mute-state');
    const muteBtnText = document.getElementById('btn-mute-text');
    if (isMuted) {
      muteVal.textContent = 'MUTED';
      muteVal.style.color = 'var(--accent-rose)';
      muteBtnText.textContent = 'Unmute Device';
    } else {
      muteVal.textContent = 'ACTIVE';
      muteVal.style.color = 'var(--accent-emerald)';
      muteBtnText.textContent = 'Mute Device';
    }
  }

  // Update recent episodic events table
  if (data.recent_events) {
    renderEventsTable(data.recent_events);
  }
}

function renderEventsTable(events) {
  const tbody = document.getElementById('events-table-body');
  if (!tbody) return;

  if (events.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center">No symbolic events recorded yet.</td></tr>';
    return;
  }

  tbody.innerHTML = events.map(evt => {
    const dt = new Date(evt.timestamp * 1000).toLocaleTimeString();
    return `
      <tr>
        <td>${dt}</td>
        <td><strong>${evt.label}</strong></td>
        <td>${(evt.confidence * 100).toFixed(0)}%</td>
        <td>Cell (${evt.grid_cell.join(', ')})</td>
        <td><span class="badge-tag ${evt.event_type}">${evt.event_type}</span></td>
        <td>
          <button class="btn btn-sm btn-outline" onclick="sendFeedback('${evt.label}', 'dismiss')">Dismiss</button>
        </td>
      </tr>
    `;
  }).join('');
}

// User Actions
async function sendFeedback(label, type, reason = 'web dashboard action') {
  if (!authToken) return;
  try {
    await fetch(`/api/feedback?token=${encodeURIComponent(authToken)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label, feedback_type: type, reason }),
    });
    fetchStatus();
  } catch (err) {
    console.error('Feedback error:', err);
  }
}

async function toggleMute() {
  if (!authToken) return;
  try {
    await fetch(`/api/control/mute?token=${encodeURIComponent(authToken)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ muted: !isMuted }),
    });
    fetchStatus();
  } catch (err) {
    console.error('Mute toggle error:', err);
  }
}

// Attach UI Event Listeners
document.getElementById('btn-mute')?.addEventListener('click', toggleMute);
document.getElementById('btn-snooze')?.addEventListener('click', () => sendFeedback('all', 'snooze', 'user requested snooze'));
document.getElementById('btn-dismiss')?.addEventListener('click', () => sendFeedback('current', 'dismiss', 'user dismissed current alert'));
document.getElementById('btn-refresh-history')?.addEventListener('click', fetchStatus);

// WebSocket real-time connection
function connectWebSocket() {
  if (!authToken) return;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(authToken)}`;

  socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    const ind = document.getElementById('ws-status');
    const txt = document.getElementById('ws-status-text');
    if (ind && txt) {
      ind.querySelector('.dot-indicator').className = 'dot-indicator dot-green';
      txt.textContent = 'Connected (Live)';
    }
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleLiveMessage(data);
    } catch (e) {
      console.warn('WS message parse error:', e);
    }
  };

  socket.onclose = () => {
    const ind = document.getElementById('ws-status');
    const txt = document.getElementById('ws-status-text');
    if (ind && txt) {
      ind.querySelector('.dot-indicator').className = 'dot-indicator dot-yellow';
      txt.textContent = 'Disconnected (Reconnecting...)';
    }
    setTimeout(connectWebSocket, 3000);
  };
}

function handleLiveMessage(msg) {
  if (msg.type === 'agent_decision') {
    const stream = document.getElementById('decision-log');
    if (stream) {
      const card = document.createElement('div');
      card.className = `decision-card ${msg.decision === 'alert' ? 'alert' : ''}`;
      card.innerHTML = `
        <span class="decision-time">${new Date().toLocaleTimeString()}</span>
        <span class="decision-action">${msg.decision.toUpperCase()}: ${msg.label || ''}</span>
        <span class="decision-reason">${msg.reason || ''}</span>
      `;
      stream.prepend(card);
    }
  } else if (msg.type === 'detections_update') {
    const container = document.getElementById('detections-container');
    if (container && msg.detections) {
      if (msg.detections.length === 0) {
        container.innerHTML = '<div class="empty-state">No objects currently requiring intervention. Monitoring environment...</div>';
      } else {
        container.innerHTML = msg.detections.map(d => `
          <div class="detection-item">
            <span class="item-label">${d.label}</span>
            <span class="item-meta">Conf: ${(d.confidence * 100).toFixed(0)}% | Cell: [${d.grid_cell.join(', ')}]</span>
          </div>
        `).join('');
      }
    }
  }
}

// Initial Boot
fetchStatus();
connectWebSocket();
setInterval(fetchStatus, 5000);
