# AI Crucible - War Room Dashboard

Real-time visualization of adversarial security testing.

## 🚀 Quick Start

### Backend (FastAPI WebSocket Server)

```bash
cd backend
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m src.server
```

Server runs on `http://localhost:8000`

### Frontend (Next.js Dashboard)

```bash
cd frontend
npm install
npm run dev
```

Dashboard runs on `http://localhost:3000`

## 📋 Features

- **Real-time WebSocket streaming** - Live updates from simulation
- **Network Graph** - Interactive React Flow visualization
- **Security Score** - Live score tracking with animations
- **Agent Activity** - Red Team vs Defender visualization
- **Mock Mode** - Development mode without API costs

## 🎨 Tech Stack

**Backend:**
- FastAPI
- WebSockets
- Python 3.10+

**Frontend:**
- Next.js 15
- React Flow
- Framer Motion
- Zustand
- Tailwind CSS

## 🔧 Development

The backend includes a mock server that sends realistic simulation events without calling real LLM APIs. Perfect for frontend development!

Set `use_mock: true` in the WebSocket message to use mock data.

## 📡 WebSocket Protocol

See `frontend/types/events.ts` for full event definitions.

Key events:
- `SYSTEM_INIT` - Simulation starts
- `COMPONENT_CREATED` - New component added
- `AGENT_SPAWN` - Agent appears
- `VULNERABILITY_FOUND` - Vulnerability discovered
- `PATCH_APPLIED` - Patch applied
- `SCORE_UPDATE` - Security score updated
- `SIMULATION_END` - Simulation complete

## 🎯 Next Steps

- [ ] Add vulnerability details panel
- [ ] Implement pause/resume controls
- [ ] Add sound effects
- [ ] Create landing page
- [ ] Deploy to production
