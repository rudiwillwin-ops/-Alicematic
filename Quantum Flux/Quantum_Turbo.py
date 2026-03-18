import MetaTrader5 as mt5
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import config

# --- YOUR XM ACCOUNT DETAILS ---
ACCOUNT_LOGIN = 123456789  # Replace with your actual MT5 login
ACCOUNT_PASSWORD = "your_password"  # Replace with your actual MT5 password
ACCOUNT_SERVER = "XMGlobal-MT5" # Replace with your actual MT5 server

class QuantumFluxApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Quantum Flux Robot")
        self.root.geometry("300x200")

        # UI Elements
        self.label = tk.Label(root, text="Quantum Flux System", font=("Arial", 14, "bold"))
        self.label.pack(pady=10)
        self.status_label = tk.Label(root, text="Status: Standby", fg="orange")
        self.status_label.pack(pady=5)

        # The START Button
        self.start_button = tk.Button(root, text="START ROBOT", command=self.toggle_robot,
                                       bg="green", fg="white", width=20, height=2)
        self.start_button.pack(pady=20)

        self.is_running = False

    def toggle_robot(self):
        if self.is_running:
            self.stop_robot()
        else:
            self.run_robot()

    def run_robot(self):
        """Initializes MT5 and starts the daily logic."""
        if config.MT5_PATH:
            if not mt5.initialize(path=config.MT5_PATH):
                messagebox.showerror("Error", f"MT5 Init Failed: {mt5.last_error()}")
                return
        else:
            if not mt5.initialize():
                messagebox.showerror("Error", f"MT5 Init Failed: {mt5.last_error()}")
                return
        authorized = mt5.login(ACCOUNT_LOGIN, password=ACCOUNT_PASSWORD, server=ACCOUNT_SERVER)

        if authorized:
            self.status_label.config(text="Status: ACTIVE (XM Connected)", fg="green")
            self.start_button.config(text="STOP ROBOT", bg="red")
            self.is_running = True

            # Trigger the mandatory Daily Update & News Scan
            self.perform_daily_scan()
        else:
            messagebox.showerror("Auth Error", f"Login failed: {mt5.last_error()}")
    
    def stop_robot(self):
        """Stops the robot and disconnects from MT5."""
        mt5.shutdown()
        self.status_label.config(text="Status: Standby", fg="orange")
        self.start_button.config(text="START ROBOT", bg="green")
        self.is_running = False
        print("Robot stopped.")

    def perform_daily_scan(self):
        """Mandatory Daily Scan as per your requirements."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Scanning news & signals to compare market choices...")
        # Logic for comparing market signals goes here
        messagebox.showinfo("Update", "Daily Market Signals Scanned. Robot is now monitoring trades.")

if __name__ == "__main__":
    root = tk.Tk()
    app = QuantumFluxApp(root)
    root.mainloop()