# Quantum Breakout v1

This is a trading bot that uses a Bollinger Band squeeze strategy to identify potential breakout opportunities. The application provides a simple user interface to control the bot and switch between two trading modes: "Conservative" and "Aggressive".

## Project Structure

- `Quantum_Turbo.py`: The main application file. It contains the GUI (built with Tkinter) and the core trading logic.
- `config.py`: The configuration file. Here you can set API keys, risk management parameters, and trading pairs.
- `Roadmap.txt`: The original project requirements.
- `BACKUPS/`: A directory where backups of the project files are stored.

## How to Run

1.  **Install dependencies:** This project uses only Python's standard libraries, so no special installation is required.
2.  **Configure the bot:** Open `config.py` and replace `"YOUR_API_KEY"` and `"YOUR_API_SECRET"` with your actual trading account credentials. You can also adjust the risk parameters and trading pairs in this file.
3.  **Run the application:** Execute the `Quantum_Turbo.py` file from your terminal:
    ```
    python Quantum_Turbo.py
    ```

## How to Use

-   **Select a Trading Mode:**
    -   **Conservative Mode:** Scans a single currency pair with standard Bollinger Band settings.
    -   **Aggressive Mode:** Scans a list of five currency pairs with a more sensitive "squeeze" detection.
-   **Start/Stop the Bot:** Click the "START" button to begin trading. The button will change to "STOP", and the status bar will show the bot's current activity. Click "STOP" to pause the bot.
-   **Backup:** Use the "File" -> "Backup Project" menu option to create a zip archive of the project files in the `BACKUPS` directory.

**Disclaimer:** This is a simulated trading bot. The trading logic is based on a simplified model and is not intended for use with real money without extensive backtesting and further development.
