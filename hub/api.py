# hub/api.py
from fastapi import FastAPI, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import glob, json, os, time, subprocess, pathlib, signal, threading
from collections import deque
from typing import Dict, List

from .discovery import visa_scan, quick_lan_sweep
from .ai_dashboard import ai_dashboard
from .lab_assistant import lab_assistant
import yaml

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

DATA_DIR = "data"

# --- simple in-process registry of launched sidecars
_started: Dict[str, subprocess.Popen] = {}
_registry_lock = threading.Lock()

def _latest_file(device: str) -> str | None:
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*", f"{device}.ndjson")))
    return files[-1] if files else None

def latest_record(device: str = "scope1") -> dict:
    path = _latest_file(device)
    if not path:
        return {}
    last_line = ""
    with open(path, "r") as f:
        for last_line in f:
            pass
    return json.loads(last_line) if last_line else {}

def last_n_records(device: str = "scope1", n: int = 200) -> List[dict]:
    path = _latest_file(device)
    if not path:
        return []
    out: List[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in deque(f, maxlen=n):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out

def _abs(p: str) -> str:
    return str(pathlib.Path(p).resolve())

def _launch_sidecar(cfg_path: str) -> bool:
    """Start generic sidecar for config; track process by device name."""
    cfg = yaml.safe_load(open(cfg_path, "r"))
    name = cfg["name"]
    with _registry_lock:
        if name in _started and _started[name].poll() is None:
            # already running
            return True
        cmd = ["python", "sidecars/generic_sidecar.py", cfg_path]
        env = os.environ.copy()
        proc = subprocess.Popen(cmd, env=env)
        _started[name] = proc
    return True

def _stop_sidecar(name: str) -> bool:
    with _registry_lock:
        proc = _started.get(name)
        if not proc:
            return False
        if proc.poll() is None:
            try:
                proc.send_signal(signal.SIGTERM)
            except Exception:
                pass
        _started.pop(name, None)
    return True

@app.get("/latest")
def latest(device: str = "scope1"):
    return latest_record(device)

@app.get("/history")
def history(n: int = 200, device: str = "scope1"):
    return JSONResponse(last_n_records(device, n))

# ---------- AI Dashboard Endpoints ----------
@app.get("/ai/dashboard")
def ai_dashboard_endpoint():
    """Get real-time AI dashboard data"""
    return ai_dashboard.get_dashboard()

@app.get("/ai/insights")
def ai_insights():
    """Get AI insights and recommendations"""
    return ai_dashboard.get_ai_insights()

@app.get("/ai/alerts")
def ai_alerts(limit: int = 20):
    """Get recent AI alerts"""
    dashboard_data = ai_dashboard.get_dashboard()
    alerts = dashboard_data.get('alerts', [])
    return alerts[-limit:] if limit > 0 else alerts

@app.get("/ai/health")
def ai_health():
    """Get system health assessment"""
    insights = ai_dashboard.get_ai_insights()
    return insights.get('system_health', {})

# ---------- Lab Assistant Chat Endpoints ----------
@app.post("/chat")
def chat(message: dict = Body(...)):
    """Chat with the lab assistant"""
    user_message = message.get("message", "")
    if not user_message:
        return {"error": "No message provided"}
    
    response = lab_assistant.chat(user_message)
    return {"response": response}

@app.post("/chat/action")
def execute_action(action: dict = Body(...)):
    """Execute an action suggested by the assistant"""
    action_name = action.get("action", "")
    parameters = action.get("parameters", {})
    
    if not action_name:
        return {"error": "No action specified"}
    
    result = lab_assistant.execute_action(action_name, parameters)
    return {"result": result}

@app.get("/debug")
def debug_page():
    """Debug page for troubleshooting chart issues"""
    with open("debug.html", "r") as f:
        return HTMLResponse(f.read())

# ---------- Discovery & onboarding ----------
@app.get("/discover/visa")
def discover_visa():
    return visa_scan()

@app.get("/discover/lan")
def discover_lan(subnet: str = "192.168.1.0/24"):
    return quick_lan_sweep(subnet)

@app.get("/devices/running")
def devices_running():
    with _registry_lock:
        out = []
        for name, proc in _started.items():
            out.append({"name": name, "pid": proc.pid, "alive": proc.poll() is None})
        return out

@app.post("/onboard")
def onboard(device: dict = Body(...)):
    """
    Example JSON body:

    # Hardware (SCPI over TCP)
    {
      "name": "scope1",
      "driver": "drivers.rigol.mso_basic",
      "resource": "TCPIP0::192.168.1.50::5025::SOCKET",
      "poll_hz": 0.5,
      "mqtt_host": "localhost",
      "mqtt_port": 1883
    }

    # Demo (no hardware)
    {
      "name": "demo1",
      "driver": "drivers.demo.random_meter",
      "poll_hz": 1.0,
      "mqtt_host": "localhost",
      "mqtt_port": 1883
    }
    """
    os.makedirs("config", exist_ok=True)
    cfg_path = f"config/{device['name']}.yaml"
    with open(cfg_path, "w") as f:
        yaml.safe_dump(device, f, sort_keys=False)
    ok = _launch_sidecar(_abs(cfg_path))
    return {"ok": ok, "config": _abs(cfg_path)}


@app.post("/devices/stop")
def stop_device(body: dict = Body(...)):
    """
    { "name": "scope1" }
    """
    name = body["name"]
    ok = _stop_sidecar(name)
    return {"ok": ok, "name": name}

# ---------- Enhanced Main Page with AI ----------
# ---------- Simple Working Version with AI Dashboard Only ---------- # NEW
@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Lab-OS Live</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body { 
      background: #1a1f3a; 
      color: #e7e7e7; 
      font-family: monospace; 
      margin: 0; 
      padding: 20px; 
    }
    .wrap { max-width: 1200px; margin: 0 auto; }
    .card { 
      background: #2a1f3a; 
      border-radius: 16px; 
      padding: 20px; 
      margin: 20px 0; 
      border-left: 4px solid #6bcf7f; 
    }
    .ai-card { 
      background: #1f2a3a; 
      border-left: 4px solid #9fd1ff; 
    }
    .chart-container { 
      width: 100%; 
      height: 400px; 
      margin: 20px 0; 
      border: 2px solid #6bcf7f; 
      border-radius: 8px; 
      padding: 10px; 
    }
    canvas { width: 100% !important; height: 100% !important; }
    h1 { color: #9fd1ff; margin-bottom: 10px; }
    .status { color: #6bcf7f; font-size: 14px; }
    pre { 
      background: #1f2a3a; 
      padding: 15px; 
      border-radius: 8px; 
      overflow: auto; 
      max-height: 200px; 
    }
    .row { display: flex; gap: 20px; flex-wrap: wrap; }
    .col { flex: 1; min-width: 300px; }
    .health-score { font-size: 24px; font-weight: bold; }
    .health-excellent { color: #6bcf7f; }
    .health-good { color: #ffd93d; }
    .health-fair { color: #ff9f43; }
    .health-poor { color: #ff6b6b; }
    .alert { padding: 8px; margin: 4px 0; border-radius: 8px; font-size: 12px; }
    .alert.critical { background: #4a1f1f; border-left: 4px solid #ff6b6b; }
    .alert.warning { background: #4a3f1f; border-left: 4px solid #ffd93d; }
    .alert.info { background: #1f4a3f; border-left: 4px solid #6bcf7f; }
    .nav { margin-bottom: 20px; }
    .nav a { 
      color: #9fd1ff; 
      text-decoration: none; 
      padding: 8px 16px; 
      border: 1px solid #9fd1ff; 
      border-radius: 8px; 
      margin-right: 10px; 
    }
    .nav a:hover { background: #9fd1ff; color: #1a1f3a; }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js"></script>
</head>
<body>
<div class="wrap">
  <h1>Lab-OS Live</h1>
  <div class="status">device: scope1 • updates every 1s</div>
  
  <div class="nav">
    <a href="/">📊 Dashboard</a>
    <a href="/ai">🤖 AI Assistant</a>
  </div>
  
  <div class="card">
    <h3>📊 Voltage</h3>
    <div class="chart-container">
      <canvas id="voltage"></canvas>
    </div>
  </div>
  
  <div class="card">
    <h3>⚡ Current</h3>
    <div class="chart-container">
      <canvas id="current"></canvas>
    </div>
  </div>
  
  <div class="row">
    <div class="col">
      <div class="card ai-card">
        <h3>🤖 AI Dashboard</h3>
        <div id="ai-summary">Loading AI insights...</div>
        <div id="ai-alerts"></div>
      </div>
    </div>
    <div class="col">
      <div class="card ai-card">
        <h3>📊 System Health</h3>
        <div id="health-score" class="health-score">--</div>
        <div id="health-details"></div>
      </div>
    </div>
  </div>
  
  <div class="card">
    <h3>📋 Latest Data</h3>
    <pre id="json">Loading...</pre>
  </div>
</div>

<script>
console.log('Lab-OS starting...');

const device = "scope1";
const fmt = ts => new Date(ts*1000).toLocaleTimeString();
const maxPoints = 100;

// Create charts
const vChart = new Chart(document.getElementById('voltage').getContext('2d'), {
  type: 'line',
  data: { 
    labels: [], 
    datasets: [{ 
      label: 'Voltage', 
      data: [], 
      borderColor: '#9fd1ff',
      backgroundColor: 'rgba(159, 209, 255, 0.1)',
      borderWidth: 2,
      fill: false
    }] 
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: { 
      x: { 
        grid: { color: 'rgba(255,255,255,0.1)' },
        ticks: { color: '#e7e7e7' }
      }, 
      y: { 
        grid: { color: 'rgba(255,255,255,0.1)' },
        ticks: { color: '#e7e7e7' }
      } 
    },
    plugins: { 
      legend: { 
        labels: { color: '#e7e7e7' }
      } 
    }
  }
});

const cChart = new Chart(document.getElementById('current').getContext('2d'), {
  type: 'line',
  data: { 
    labels: [], 
    datasets: [{ 
      label: 'Current', 
      data: [], 
      borderColor: '#ff6b6b',
      backgroundColor: 'rgba(255, 107, 107, 0.1)',
      borderWidth: 2,
      fill: false
    }] 
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: { 
      x: { 
        grid: { color: 'rgba(255,255,255,0.1)' },
        ticks: { color: '#e7e7e7' }
      }, 
      y: { 
        grid: { color: 'rgba(255,255,255,0.1)' },
        ticks: { color: '#e7e7e7' }
      } 
    },
    plugins: { 
      legend: { 
        labels: { color: '#e7e7e7' }
      } 
    }
  }
});

console.log('Charts created');

function addPoint(d) {
  console.log('Adding point:', d);
  const label = fmt(d.ts);
  
  vChart.data.labels.push(label);
  vChart.data.datasets[0].data.push(d.voltage || 0);
  
  cChart.data.labels.push(label);
  cChart.data.datasets[0].data.push(d.current || 0);
  
  // Keep only last maxPoints
  if (vChart.data.labels.length > maxPoints) {
    vChart.data.labels.shift();
    vChart.data.datasets[0].data.shift();
  }
  if (cChart.data.labels.length > maxPoints) {
    cChart.data.labels.shift();
    cChart.data.datasets[0].data.shift();
  }
  
  vChart.update();
  cChart.update();
  
  document.getElementById('json').textContent = JSON.stringify(d, null, 2);
}

async function loadHistory() {
  try {
    console.log('Loading history...');
    const res = await fetch(`/history?n=50&device=${device}`);
    const data = await res.json();
    console.log('Loaded', data.length, 'points');
    
    data.forEach(addPoint);
  } catch(e) {
    console.error('History error:', e);
  }
}

async function poll() {
  try {
    const res = await fetch(`/latest?device=${device}`);
    if (res.ok) {
      const data = await res.json();
      if (data && data.ts) {
        addPoint(data);
      }
    }
  } catch(e) {
    console.error('Poll error:', e);
  }
}

// AI Dashboard Functions
async function updateAIDashboard() {
  try {
    console.log('Updating AI dashboard...');
    const res = await fetch('/ai/insights');
    if (res.ok) {
      const insights = await res.json();
      console.log('AI insights:', insights);
      
      // Update health score
      const healthScore = insights.system_health.overall_score;
      const healthEl = document.getElementById('health-score');
      if (healthEl) {
        healthEl.textContent = Math.round(healthScore * 100) + '%';
        healthEl.className = 'health-score health-' + insights.system_health.status;
      }
      
      // Update health details
      const healthDetailsEl = document.getElementById('health-details');
      if (healthDetailsEl) {
        healthDetailsEl.innerHTML = `
          <div>Status: ${insights.system_health.status}</div>
          <div>Healthy devices: ${insights.system_health.devices_healthy}</div>
          <div>Devices at risk: ${insights.system_health.devices_at_risk}</div>
        `;
      }
      
      // Update AI summary
      const aiSummaryEl = document.getElementById('ai-summary');
      if (aiSummaryEl) {
        aiSummaryEl.innerHTML = `
          <div>System Status: ${insights.system_health.status}</div>
          <div>Overall Health: ${Math.round(healthScore * 100)}%</div>
        `;
      }
      
      // Update recommendations
      const alertsEl = document.getElementById('ai-alerts');
      if (alertsEl) {
        alertsEl.innerHTML = insights.recommendations.map(rec => 
          `<div class="alert ${rec.type}">
            <strong>${rec.type.toUpperCase()}:</strong> ${rec.message}<br>
            <em>${rec.action}</em>
          </div>`
        ).join('');
      }
    }
  } catch(e) { 
    console.error('AI dashboard update failed:', e);
  }
}

// Start everything
loadHistory().then(() => {
  console.log('Starting polling...');
  setInterval(poll, 1000);
  setInterval(updateAIDashboard, 5000);
  updateAIDashboard();
});
</script>
</body>
</html>
""")

# ---------- Separate AI Chat Page ---------- # NEW
@app.get("/ai", response_class=HTMLResponse)
def ai_chat():
    return HTMLResponse("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Lab-OS AI Assistant</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body { 
      background: #1a1f3a; 
      color: #e7e7e7; 
      font-family: monospace; 
      margin: 0; 
      padding: 20px; 
    }
    .wrap { max-width: 800px; margin: 0 auto; }
    .card { 
      background: #2a1f3a; 
      border-radius: 16px; 
      padding: 20px; 
      margin: 20px 0; 
      border-left: 4px solid #ff6b6b; 
    }
    h1 { color: #9fd1ff; margin-bottom: 10px; }
    .nav { margin-bottom: 20px; }
    .nav a { 
      color: #9fd1ff; 
      text-decoration: none; 
      padding: 8px 16px; 
      border: 1px solid #9fd1ff; 
      border-radius: 8px; 
      margin-right: 10px; 
    }
    .nav a:hover { background: #9fd1ff; color: #1a1f3a; }
    .chat-input { 
      width: 70%; 
      padding: 12px; 
      border: none; 
      border-radius: 8px; 
      background: #1f2a3a; 
      color: #e7e7e7; 
      margin-right: 8px; 
      font-size: 14px;
    }
    .chat-button { 
      padding: 12px 24px; 
      border: none; 
      border-radius: 8px; 
      background: #ff6b6b; 
      color: white; 
      cursor: pointer; 
      font-size: 14px;
    }
    .chat-button:hover { background: #ff5252; }
    .chat-messages { 
      max-height: 400px; 
      overflow-y: auto; 
      background: #1f2a3a; 
      padding: 15px; 
      border-radius: 8px; 
      margin-top: 15px; 
    }
    .chat-message { 
      padding: 12px; 
      margin: 8px 0; 
      border-radius: 8px; 
      line-height: 1.4;
    }
    .chat-user { background: #1f4a3f; }
    .chat-assistant { background: #4a1f3f; }
    .status { color: #6bcf7f; font-size: 14px; margin-bottom: 20px; }
  </style>
</head>
<body>
<div class="wrap">
  <h1>🤖 Lab-OS AI Assistant</h1>
  <div class="status">Ask me anything about your lab experiments, data, or instruments!</div>
  
  <div class="nav">
    <a href="/">📊 Dashboard</a>
    <a href="/ai">🤖 AI Assistant</a>
  </div>
  
  <div class="card">
    <h3>💬 Chat with AI</h3>
    <div>
      <input type="text" id="chat-input" class="chat-input" placeholder="Ask me anything about your lab..." />
      <button onclick="sendChatMessage()" class="chat-button">Send</button>
    </div>
    <div id="chat-messages" class="chat-messages"></div>
  </div>
</div>

<script>
console.log('AI Assistant starting...');

// Chat Functions - Define addChatMessage first
function addChatMessage(role, content) {
  const messagesEl = document.getElementById('chat-messages');
  if (!messagesEl) return;
  
  const messageEl = document.createElement('div');
  messageEl.className = `chat-message chat-${role}`;
  messageEl.textContent = content;
  messagesEl.appendChild(messageEl);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  if (!message) return;
  
  console.log('Sending chat message:', message);
  
  // Add user message
  addChatMessage('user', message);
  input.value = '';
  
  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message })
    });
    
    console.log('Chat response status:', response.status);
    const data = await response.json();
    console.log('Chat response:', data);
    addChatMessage('assistant', data.response);
  } catch(e) {
    console.error('Chat error:', e);
    addChatMessage('assistant', 'Sorry, I encountered an error. Please try again.');
  }
}

// Add Enter key support
document.getElementById('chat-input').onkeypress = function(e) {
  if (e.key === 'Enter') {
    sendChatMessage();
  }
};

// Welcome message - now addChatMessage is defined
addChatMessage('assistant', 'Hello! I\'m your lab assistant. Ask me anything about your experiments, data, or instruments!');
</script>
</body>
</html>
""")

# ---------- Simple Test Route ----------
@app.get("/test", response_class=HTMLResponse)
def test_page():
    """Fixed test page with proper chart styling"""
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Chart Test - Fixed</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .chart-container { 
            width: 600px; 
            height: 400px; 
            border: 2px solid #ccc; 
            margin: 20px 0; 
            position: relative;
        }
        canvas { 
            width: 100% !important; 
            height: 100% !important; 
        }
        .status { 
            padding: 10px; 
            margin: 10px 0; 
            border-radius: 5px; 
        }
        .success { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <h1>Chart Test - Fixed</h1>
    <div id="status"></div>
    <div class="chart-container">
        <canvas id="testChart"></canvas>
    </div>
    
    <script>
        console.log('Starting fixed chart test...');
        
        function updateStatus(message, isSuccess = true) {
            const statusEl = document.getElementById('status');
            statusEl.innerHTML = `<div class="status ${isSuccess ? 'success' : 'error'}">${message}</div>`;
        }
        
        // Test Chart.js
        if (typeof Chart === 'undefined') {
            console.error('Chart.js not loaded!');
            updateStatus('❌ Chart.js failed to load', false);
        } else {
            console.log('✅ Chart.js loaded successfully');
            updateStatus('✅ Chart.js loaded successfully');
            
            // Create a simple chart with proper configuration
            const ctx = document.getElementById('testChart').getContext('2d');
            const chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: ['1', '2', '3', '4', '5'],
                    datasets: [{
                        label: 'Test Data',
                        data: [1, 2, 3, 2, 1],
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        borderWidth: 2,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
            console.log('✅ Chart created successfully');
            updateStatus('✅ Chart created successfully');
        }
        
        // Test API
        async function testAPI() {
            try {
                console.log('Testing API...');
                const response = await fetch('/latest?device=scope1');
                console.log('API response status:', response.status);
                
                if (response.ok) {
                    const data = await response.json();
                    console.log('✅ API working, data:', data);
                    updateStatus('✅ API working! Data received: ' + JSON.stringify(data).substring(0, 100) + '...');
                } else {
                    console.error('API error:', response.status);
                    updateStatus('❌ API error: ' + response.status, false);
                }
            } catch (e) {
                console.error('API test failed:', e);
                updateStatus('❌ API test failed: ' + e.message, false);
            }
        }
        
        testAPI();
    </script>
</body>
</html>
""")

# ---------- Ultra Simple Test Route ----------
@app.get("/simple", response_class=HTMLResponse)
def simple_test():
    """Ultra simple test to check if JavaScript works at all"""
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Ultra Simple Test</title>
</head>
<body>
    <h1>Ultra Simple Test</h1>
    <div id="result">Loading...</div>
    
    <script>
        console.log('JavaScript starting...');
        document.getElementById('result').innerHTML = 'JavaScript is working! ✅';
        console.log('JavaScript finished!');
    </script>
</body>
</html>
""")

# ---------- Minimal Test Route ----------
@app.get("/minimal", response_class=HTMLResponse)
def minimal_test():
    """Minimal test to debug the exact issue"""
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Minimal Test</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js"></script>
    <style>
        body { background: #1a1f3a; color: #e7e7e7; font-family: monospace; }
        .chart-container { width: 600px; height: 400px; margin: 20px; border: 2px solid #6bcf7f; }
        canvas { width: 100% !important; height: 100% !important; }
    </style>
</head>
<body>
    <h1>Minimal Chart Test</h1>
    <div class="chart-container">
        <canvas id="testChart"></canvas>
    </div>
    <div id="status">Loading...</div>
    
    <script>
        console.log('Minimal test starting...');
        
        // Test Chart.js
        if (typeof Chart === 'undefined') {
            document.getElementById('status').innerHTML = '❌ Chart.js failed to load';
            console.error('Chart.js not loaded!');
        } else {
            console.log('✅ Chart.js loaded');
            
            // Create chart
            const ctx = document.getElementById('testChart').getContext('2d');
            const chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: ['1', '2', '3', '4', '5'],
                    datasets: [{
                        label: 'Test Data',
                        data: [1, 2, 3, 2, 1],
                        borderColor: '#9fd1ff',
                        backgroundColor: 'rgba(159, 209, 255, 0.1)',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.1)' } },
                        y: { grid: { color: 'rgba(255,255,255,0.1)' } }
                    }
                }
            });
            
            console.log('✅ Chart created');
            document.getElementById('status').innerHTML = '✅ Chart created successfully!';
        }
    </script>
</body>
</html>
""")

