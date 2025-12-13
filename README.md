virtual_assistant/
├── .env                          # SECRETS: Unraid IP, API Keys, DB Passwords
├── .gitignore                    # GIT: Exclude .env, __pycache__, and local DBs
├── pyproject.toml                # PACKAGE: Allows "pip install -e ." (Critical for imports)
├── main.py                       # ENTRY POINT: The FastAPI server or CLI runner
│
├── src/
│   ├── core/                     # INFRASTRUCTURE (The "Plumbing")
│   │   ├── __init__.py
│   │   ├── config.py             # SETTINGS: Loads .env, validates Unraid IP/paths
│   │   ├── logging.py            # UTILS: Centralized JSON/Color logging setup
│   │   ├── security.py           # SAFETY: Whitelist of allowed shell commands
│   │   │
│   │   ├── llm.py                # FACTORY: Returns ChatOllama / OllamaLLM
│   │   ├── vector.py             # FACTORY: Returns QdrantClient (Knowledge)
│   │   ├── persistence.py        # FACTORY: Returns LangGraph Checkpointer (State)
│   │   ├── database.py           # FACTORY: Returns SQL Connection (Structured Data)
│   │   ├── documents.py          # FACTORY: Returns Paperless HTTP Session
│   │   └── iot.py                # FACTORY: Returns Home Assistant API Client
│   │
│   ├── orchestrator/             # THE BRAIN (The "Supervisor")
│   │   ├── __init__.py
│   │   ├── graph.py              # LOGIC: The Master LangGraph Workflow definition
│   │   ├── state.py              # SCHEMA: GlobalState TypedDict (The "Memory Shape")
│   │   └── prompts.py            # TEXT: System prompts for the Router/Supervisor
│   │
│   ├── capabilities/             # THE SKILLS (Vertical Slices)
│   │   ├── __init__.py
│   │   │
│   │   ├── home_control/         # DOMAIN: Home Assistant
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Sub-graph for "Smart Home" logic
│   │   │   └── tools.py          # Tools: toggle_light, get_temperature
│   │   │
│   │   ├── finance/              # DOMAIN: Money/Banking
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Sub-graph for "Financial" logic
│   │   │   └── tools.py          # Tools: get_monthly_spend (uses core.database)
│   │   │
│   │   ├── research/             # DOMAIN: Knowledge/RAG
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Sub-graph for "Lookup" logic
│   │   │   ├── tools.py          # Tools: search_knowledge_base (uses core.vector)
│   │   │   └── loader.py         # ETL: Script to scrape Paperless -> Qdrant
│   │   │
│   │   └── dynamic/              # DOMAIN: Self-Modification (Biohazard Zone)
│   │       ├── __init__.py
│   │       └── generated/        # FOLDER: Where the agent writes new .py tools
│   │
│   └── utils/                    # SHARED UTILITIES
│       ├── __init__.py
│       ├── parsing.py            # HELPERS: Clean LLM JSON output
│       └── formatting.py         # HELPERS: Pretty print tables/dates
│
└── tests/                        # INTEGRATION TESTS
    ├── capabilities/
    │   ├── test_finance.py
    │   └── test_home_control.py
    └── orchestrator/
        └── test_graph.py