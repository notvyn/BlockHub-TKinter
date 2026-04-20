import tkinter as tk
from tkinter import ttk
from datetime import datetime, time

class TimePicker(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, bg="white", *args, **kwargs)
        
        # 1. Update Grid to handle 4 columns (Hour, Colon, Minute, AM/PM)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.columnconfigure(2, weight=1)
        self.columnconfigure(3, weight=1) # New column for AM/PM

        # Hour Combobox (1 to 12)
        self.hour_cb = ttk.Combobox(self, values=[f"{i:02d}" for i in range(1, 13)], state="readonly", font=("Arial", 12), justify="center")
        self.hour_cb.grid(row=0, column=0, sticky="ew", ipady=5)

        # Colon
        colon_label = tk.Label(self, text=":", font=("Arial", 14, "bold"), bg="white")
        colon_label.grid(row=0, column=1, padx=2)

        # Minute Combobox
        self.minute_cb = ttk.Combobox(self, values=[f"{i:02d}" for i in range(0, 60, 5)], state="readonly", font=("Arial", 12), justify="center")
        self.minute_cb.grid(row=0, column=2, sticky="ew", ipady=5)

        # AM/PM Combobox
        self.ampm_cb = ttk.Combobox(self, values=["AM", "PM"], state="readonly", font=("Arial", 12), justify="center", width=4)
        self.ampm_cb.grid(row=0, column=3, sticky="ew", padx=(5, 0), ipady=5)

    def get(self):
        """Translates the 12-hour UI back into 24-hour format for the database."""
        h = self.hour_cb.get()
        m = self.minute_cb.get()
        ampm = self.ampm_cb.get()
        
        if not h or not m or not ampm:
            return "" # Return empty if they didn't fill it all out
            
        h_int = int(h)
        
        # Convert to 24-hour logic
        if ampm == "PM" and h_int != 12:
            h_int += 12
        elif ampm == "AM" and h_int == 12:
            h_int = 0
            
        return f"{h_int:02d}:{m}"

    def set(self, time_val):
        """Translates the database's 24-hour time into the 12-hour UI."""
        if not time_val:
            return
            
        # Handle string inputs (just in case) or direct datetime.time objects
        if isinstance(time_val, str):
            try:
                # Try parsing standard HH:MM
                time_val = datetime.strptime(time_val, "%H:%M").time()
            except ValueError:
                # Try parsing HH:MM:SS if seconds are attached
                time_val = datetime.strptime(time_val, "%H:%M:%S").time()
                
        h = time_val.hour
        m = time_val.minute
        
        # Figure out AM or PM
        ampm = "PM" if h >= 12 else "AM"
        
        # Convert hour to 12-hour format
        h_12 = h % 12
        if h_12 == 0:
            h_12 = 12
            
        # Set the UI widgets
        self.hour_cb.set(f"{h_12:02d}")
        self.minute_cb.set(f"{m:02d}")
        self.ampm_cb.set(ampm)

class ScrollableFrame:
    def __init__(self, parent, bg_color="white", scrollbar_color="#ECECEC", trough_color="#ECECEC"):
        # 1. Main Outer Container
        self.container = tk.Frame(parent, bg=bg_color)
        self.container.pack(fill="both", expand=True)

        # 2. Canvas (The Viewport)
        self.canvas = tk.Canvas(self.container, bg=bg_color, highlightthickness=0)

        # 3. Scrollbar & Styling
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Custom.Vertical.TScrollbar", 
                        background=scrollbar_color, 
                        troughcolor=trough_color,
                        bordercolor=scrollbar_color, 
                        arrowcolor="white")

        self.scrollbar = ttk.Scrollbar(self.container, orient="vertical", command=self.canvas.yview, style="Custom.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 4. The Inner Frame (Where your actual content goes)
        self.scrollable_frame = tk.Frame(self.canvas, bg=bg_color)
        self.window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.canvas.pack(side="left", fill="both", expand=True)

        # 5. Bindings
        self.scrollable_frame.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    # --- CLASS METHODS ---

    def _update_scroll_region(self, event=None):
        """ Dynamically shows/hides the scrollbar and updates the scrollable area """
        self.canvas.update_idletasks()
        region = self.canvas.bbox("all")
        
        if region:
            self.canvas.configure(scrollregion=region)
            
            content_height = region[3]
            visible_height = self.canvas.winfo_height()
            
            if content_height > visible_height:
                self.scrollbar.pack(side="right", fill="y")
            else:
                self.scrollbar.pack_forget()
                self.canvas.yview_moveto(0) # Snap to top if it shrinks

    def _on_canvas_configure(self, event):
        """ Ensures the inner frame stretches to the width of the canvas """
        self.canvas.itemconfig(self.window_id, width=event.width)
        self._update_scroll_region()

    def _safe_mousewheel(self, event):
        """ Only scrolls if the scrollbar is currently visible """
        try:
            # 1. Check if the widget even exists anymore
            if not self.scrollbar.winfo_exists():
                return
                
            # 2. Your existing logic
            if self.scrollbar.winfo_ismapped():
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                
        except tk.TclError:
            # If Tkinter still throws a ghost error during a fast page switch, 
            # just quietly catch it and ignore it!
            pass

    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._safe_mousewheel)

    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")