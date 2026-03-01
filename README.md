# Portfolio Manager

A Dash-based portfolio analytics and management dashboard for Indian stock portfolios. Connects to Zerodha (Kite API) to analyze holdings, track asset allocation, monitor concentration risk, and generate intelligent exit signals.

## Dashboard

The application provides an interactive web dashboard with two main tabs:
- **Portfolio Health** - Overview of all metrics and allocation status
- **Exit Signals** - Detailed scoring and recommendations for each holding

## Tech Stack

- **Backend**: Python 3
- **Web Framework**: Dash (Plotly's interactive web framework)
- **UI**: Dash Bootstrap Components
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
   python -m venv .venv
   source .venv/Scripts/activate  # Windows
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Configure credentials
   Create a `.env` file in the project root:
   ```
   API_KEY=your_zerodha_api_key
   API_SECRET=your_zerodha_api_secret
   ```

### Running the Application

```bash
python app.py
```

The dashboard will be available at `http://localhost:8050`

On first load, you'll be redirected to Zerodha login. After authentication, the dashboard will pull your holdings and display comprehensive analytics.

## Customization

### Modify Asset Categories
Edit the `CATEGORY_MAP` in [domain/portfolio.py](domain/portfolio.py) to define your own asset classes and ETF mappings.

### Adjust Allocation Targets
Update `CATEGORY_TARGETS` in [domain/allocation.py](domain/allocation.py) to set target allocation ranges for each category.

### Fine-tune Exit Signals
Modify scoring functions in [domain/exit_engine.py](domain/exit_engine.py) to adjust sensitivity of the exit engine to various risk factors.
