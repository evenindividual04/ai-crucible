# 🛡️ AI Crucible

> **"If it can be broken, it will be broken. Automatically."**

**AI Crucible** is an autonomous **Adversarial Reasoning Engine**. It doesn't just "check your code"—it simulates a war room where AI agents ruthlessly attack your system design before you write a single line of implementation.

An **Architect** designs a system. A **Red Team** of specialized experts attacks it. A **Defender** patches the holes. A **Judge** oversees the chaos.


[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange)](https://langchain-ai.github.io/langgraph/)

---

## 🚀 Why Crucible?

Most "AI coding assistants" are yes-men. They generate code that *looks* right but fails under pressure. The Crucible takes a different approach: **Adversarial Hardening.**

*   **Self-Healing Architecture**: The system iterates on its own design. It breaks it, fixes it, and breaks it again until it's solid.
*   **Specialized "Personas"**:
    *   **🦅 Security Hawk**: Hunts for auth bypasses, injections, and data leaks.
    *   **🦖 Scale Monster**: Simulates 100x traffic spikes to find bottlenecks.
    *   **💸 Cost Analyst**: Identifies "wallet-denial-of-service" risks.
    *   **🧩 Logic Breaker**: finds race conditions and state machine deadlocks.
*   **Strict Governance**: A non-LLM "Judge" ensures agents don't hallucinate progress.
*   **Provider Agnostic**: Use Google Gemini, OpenAI GPT-4, Anthropic Claude, or local Ollama models.

---

## ⚡ Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-crucible.git
cd ai-crucible

# Install dependencies (virtualenv recommended)
pip install -e ".[dev]"
```

### 2. Configuration

Create a configuration file:

```bash
crucible init
```

Set your API key in a `.env` file:

```ini
GOOGLE_API_KEY=your_key_here
# or OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
```

### 3. Run the Crucible

Give it a high-level prompt and watch the sparks fly:

```bash
crucible run "Design a secure, real-time voting system for a national election"
```

The **War Room** UI will spin up, showing you real-time attacks and patches:



---

## 📖 Usage Guide

### The "Run" Command

```bash
crucible run "<PROMPT>" [OPTIONS]
```

**Options:**
*   `--provider`: Choose LLM backend (`google`, `openai`, `anthropic`, `ollama`, `groq`).
*   `--model`: Override specific model (e.g., `gpt-4-turbo`).
*   `--max-iterations`: How many attack/defend rounds to run (default: 3).
*   `--output-design`: Save the final hardened design to a Markdown file.
*   `--json`: Output simplified JSON for CI/CD pipelines.

**Example:**
```bash
crucible run "A high-frequency trading bot in Python" \
  --provider openai \
  --model gpt-4o \
  --output-design hardened_bot.md
```

### Resume from Checkpoint

Crucible saves state automatically. If a run crashes or you want to branch off:

```bash
crucible resume ./checkpoints/run_12345.pkl
```

---

## ⚙️ Configuration

The `crucible.yaml` file controls the engine's physics:

```yaml
max_iterations: 5

similarity:
  threshold: 0.85 # Filter duplicate vulnerabilities

confidence:
  blocking_threshold: 0.7 # Ignore low-confidence hallucinations

llm:
  provider: "google"
  model: "gemini-2.5-flash"
  temperature: 0.3
```

---

## 🏗️ Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for a deep dive into the LangGraph state machine, agent taxonomy, and control flow.

---

## 🤝 Contributing

We welcome new agents! If you want to build a "Privacy Compliance Agent" or a "Chaos Monkey", check out `src/crucible/agents/` and inherit from `BaseAgent`.

1.  Fork the repo.
2.  Create your feature branch.
3.  Add your agent to the `RED_TEAM_AGENTS` registry in `graph.py`.
4.  Submit a PR!

---
