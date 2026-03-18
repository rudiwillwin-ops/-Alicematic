# 🏗️ Technical Architecture & Stack

## 1. Core Technology
*   **Language:** Python 3.11+
    *   *Reasoning:* Industry standard for Quant Finance; massive ecosystem for ML/Stats.
*   **Concurrency:** `asyncio` (Asynchronous I/O)
    *   *Reasoning:* Essential for handling WebSocket streams (market data) and Order execution in parallel without blocking.

## 2. Libraries & Frameworks
| Component | Library | Purpose |
| :--- | :--- | :--- |
| **Data Structures** | `pandas`, `numpy` | Vectorized calculations, Time-series management. |
| **Exchange API** | `ccxt` (async) | Unified API for 100+ exchanges; WebSocket support. |
| **Technical Analysis** | `pandas-ta` | High-performance indicator calculation (RSI, ATR, Bollinger, etc.). |
| **Machine Learning** | `scikit-learn` | Random Forest/XGBoost for signal weighting and regime detection. |
| **Validation** | `pydantic` | Strict data typing to prevent "garbage-in/garbage-out" errors. |
| **AI/LLM** | `google-generativeai` | Gemini API for News Sentiment & Self-Healing Ops. |
| **Logging** | `loguru` | Structured, asynchronous logging for debugging and audit trails. |

## 3. Data Persistence (Storage)
*   **Hot Storage (State):** `JSON` / In-Memory
    *   Used for: Active positions, open orders, current configuration.
*   **Cold Storage (History):** `SQLite` (Migratable to `TimescaleDB`)
    *   Used for: Trade history, audit logs, backtesting datasets.

## 4. System Architecture Diagram

```mermaid
graph TD
    A[Market Data (WebSockets)] -->|Async Stream| B(Event Loop)
    B -->|Tick Data| C{Strategy Engine}
    
    subgraph "The Brain"
    C -->|Price Data| D[Vectorized Math (Pandas/NumPy)]
    C -->|Market State| E[ML Classifier (Scikit-Learn)]
    E -->|Regime (Trend/Range)| D
    end
    
    subgraph "The Shield"
    D -->|Signal| F{Risk Manager (VaR/Kelly)}
    F -->|Go/No-Go| G[Execution Algo (TWAP/Iceberg)]
    end
    
    G -->|Order| H[Exchange API (CCXT)]
    H -->|Fill Report| I[Database (SQLite)]
    
    subgraph "The Watchtower"
    J[News Sentinel (Gemini API)] -->|Sentiment Shock| F
    end
```

## 5. Directory Structure
```
/Trading Robot
├── /config           # Settings, API Keys (Encrypted)
├── /data             # Local database, logs
├── /src
│   ├── /strategies   # Alpha logic (Trend, MeanRev, Arb)
│   ├── /core         # Engine, Event Loop, Risk Manager
│   ├── /connectors   # Exchange wrappers
│   └── /utils        # Math helpers, AI tools
├── /tests            # Unit tests, Backtests
└── main.py           # Entry point
```
