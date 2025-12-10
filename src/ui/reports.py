import tkinter as tk
from tkinter import ttk

class ReportsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Reports")
        self.geometry("800x600")
        
        label = ttk.Label(self, text="Reports Window")
        label.pack(padx=20, pady=20)
