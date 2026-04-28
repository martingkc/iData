# Agentic LLM Frontend

Interactive workspace where operators can curate document context, pick agent tools, and collaborate with an LLM.

## Quick start

```bash
cd Frontend
npm install
npm run dev
```

Then open the printed URL (default `http://localhost:5173`).

## Features

- Minimal sidebar with session list and quick actions
- Floating chat composer with folder menu, modal tool picker, and deep-search toggle
- Tool drawer with chip toggles to arm the agent per conversation
- Settings drawer placeholder for runtime configuration inputs

## Next steps

Wire the send handler to your backend agent endpoint, replacing the simulated `buildAssistantStub` helper in `src/App.tsx`. Hook both the folder picker and workspace manager into your ingestion pipeline as needed.
