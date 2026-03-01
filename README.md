# Portfolio Manager

A Dash-based portfolio analytics dashboard for Indian stock portfolios. Connects to Zerodha (Kite API) to analyze holdings, track asset allocation, monitor concentration risk, and generate intelligent exit signals.

## Dashboard

The application provides an interactive web dashboard with two main tabs:
- **Portfolio Health** — Overview of all metrics and allocation status
- **Exit Signals** — Detailed scoring and recommendations for each holding

## Project Structure

```
PortfolioManager/
├── app.py                              ← entry point
├── config/
│   └── env.py                          ← API keys from .env
├── auth/
│   └── kite_auth.py                    ← Zerodha OAuth
├── services/
│   ├── kite_service.py                 ← holdings/positions API
│   └── price_history.py                ← historical data + indicators
├── core/
│   ├── settings.py                     ← global config (CATEGORY_MAP, etc.)
│   └── portfolio.py                    ← dataframe builder, portfolio health
├── engines/
│   ├── exit_engine/
│   │   ├── settings.py                 ← scoring thresholds
│   │   └── engine.py                   ← exit signal scoring + orchestrator
│   ├── allocation_engine/
│   │   ├── settings.py                 ← target allocation ranges
│   │   └── engine.py                   ← drift detection
│   └── concentration_engine/
│       ├── settings.py                 ← concentration limits
│       └── engine.py                   ← top-N and single-stock analysis
├── dashboard/
│   ├── shell.py                        ← tab bar + content wrapper
│   ├── callbacks.py                    ← tab-switching callback
│   ├── pages/                          ← one file per tab
│   └── components/                     ← reusable UI blocks
├── tests/
└── assets/
    └── styles.css
```

## Tech Stack

- **Backend**: Python 3
- **Web Framework**: Dash (Plotly)
- **Data**: Pandas, NumPy
- **API Integration**: Kite Connect (Zerodha)
- **Authentication**: OAuth2 with Zerodha

## Setup

### Prerequisites
- Python 3.8+
- A Zerodha account with API access
- API credentials (API_KEY, API_SECRET)

### Installation

1. Clone the repository
   ```bash
   git clone <repo-url>
   cd PortfolioManager
   ```

2. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Windows
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Configure credentials — create a `.env` file in the project root:
   ```
   API_KEY=your_zerodha_api_key
   API_SECRET=your_zerodha_api_secret
   ```

### Running

```bash
python app.py
```

The dashboard will be available at `http://localhost:8050`. On first load, you'll be redirected to Zerodha login.

## Customization

### Modify Asset Categories
Edit `CATEGORY_MAP` in [core/settings.py](core/settings.py).

### Adjust Allocation Targets
Update `CATEGORY_TARGETS` in [engines/allocation_engine/settings.py](engines/allocation_engine/settings.py).

### Fine-tune Exit Signals
Adjust scoring thresholds in [engines/exit_engine/settings.py](engines/exit_engine/settings.py).

### Adjust Concentration Limits
Update `TOP_N_THRESHOLD` and `LARGEST_THRESHOLD` in [engines/concentration_engine/settings.py](engines/concentration_engine/settings.py).
