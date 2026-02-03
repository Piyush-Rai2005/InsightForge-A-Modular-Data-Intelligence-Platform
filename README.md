# 🔍 InsightForge: Modular Data Intelligence Platform

InsightForge is an autonomous data agent that combines **deterministic statistical analysis** with **Large Language Models (LLMs)** to provide deep-context business intelligence. It doesn't just calculate numbers; it reasons about them.

---

## 🧠 Intelligence Architecture
InsightForge uses an **Agentic Workflow** to process data:
1. **Perception**: Ingests structured data (CSV/Excel) and schema metadata.
2. **Reasoning**: An LLM "Brain" analyzes the schema and plans an analysis strategy.
3. **Action (Tool Use)**: The agent invokes modular Python tools (Pandas profilers, SQL-like analyzers) to extract facts.
4. **Synthesis**: Converts raw statistical output into executive-level textual insights.

---

## 🛠️ Project Structure
The project follows a clean-room architectural pattern to ensure maintainability:

```text
app/
├── main.py             # Agent Entry point & Orchestration
├── agent/
│   ├── brain.py        # LLM Logic (PydanticAI / LangGraph)
│   └── prompts.py      # System instructions & Few-shot examples
├── tools/              # THE "ARMS": Functions the agent can call
│   ├── profiler.py     # Deep stats (Pandas/NumPy)
│   └── query_engine.py # Natural language to DataFrame filtering
├── insights/           # Synthesis layer
└── reporting/          # PDF/Markdown generation
