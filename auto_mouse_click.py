"""AutoMouseClick - Desktop auto mouse click application.

A desktop application with a visual interface that provides automatic mouse
clicking at configurable frequencies, with support for background mode and
global hotkey toggling.

Author: 王五一
"""

import logging
import math
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from pynput.keyboard import Key, KeyCode, Listener as KeyboardListener
from pynput.mouse import Button, Controller

# Windows-specific imports for background clicking
if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

logger = logging.getLogger(__name__)

# Minimum click interval to protect against system overload (seconds)
_MIN_INTERVAL = 0.001


class AutoMouseClick:
    """Main application class for the auto mouse click tool."""

    # Built-in click frequency presets (clicks per second)
    PRESET_FREQUENCIES = {
        "5 次/秒": 5,
        "10 次/秒": 10,
        "20 次/秒": 20,
    }

    DEFAULT_HOTKEY = "<ctrl>+<alt>+s"
    DEFAULT_HOTKEY_DISPLAY = "Ctrl+Alt+S"

    # Background mode toggle hotkey
    BG_TOGGLE_HOTKEY = {"ctrl", "alt", "i"}
    BG_TOGGLE_DISPLAY = "Ctrl+Alt+I"

    # Color scheme
    HEADER_BG = "#2c3e50"
    HEADER_FG = "#ecf0f1"
    ACCENT = "#3498db"
    SUCCESS = "#27ae60"
    DANGER = "#e74c3c"
    WARNING = "#f39c12"
    MUTED = "#95a5a6"
    BG_COLOR = "#ecf0f1"

    def __init__(self):
        self.mouse = Controller()
        self.clicking = False
        self.click_thread = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        # Settings
        self.frequency = 5  # clicks per second
        self.background_mode = False
        self.background_position = None  # stored (x, y) for background mode

        # Current hotkey configuration
        self.hotkey_combo = self.DEFAULT_HOTKEY
        self.hotkey_display = self.DEFAULT_HOTKEY_DISPLAY

        # Hotkey recording state
        self._recording_keys = set()
        self._recording_key_names = []

        # Global keyboard listener state
        self._pressed_keys = set()
        self._keyboard_listener = None
        self._hotkey_cooldown = False
        self._bg_hotkey_cooldown = False

        # Animation state
        self._animation_after_id = None
        self._pulse_step = 0

        self._build_ui()
        self._start_keyboard_listener()

    def _build_ui(self):
        """Build the main application window and all widgets."""
        self.root = tk.Tk()
        self.root.title("AutoMouseClick - 鼠标自动点击器")
        self.root.resizable(False, False)
        self.root.configure(bg=self.BG_COLOR)

        # Apply ttk theme
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabelframe", background=self.BG_COLOR)
        style.configure(
            "TLabelframe.Label",
            background=self.BG_COLOR,
            font=("", 9, "bold"),
        )
        style.configure("TLabel", background=self.BG_COLOR)
        style.configure("TCheckbutton", background=self.BG_COLOR)
        style.configure("TRadiobutton", background=self.BG_COLOR)
        style.configure("TFrame", background=self.BG_COLOR)
        style.configure("Accent.TButton", font=("", 10, "bold"))

        # ── Header ──────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=self.HEADER_BG, height=60)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        tk.Label(
            header,
            text="\U0001f5b1 AutoMouseClick",
            font=("Segoe UI", 16, "bold"),
            bg=self.HEADER_BG,
            fg=self.HEADER_FG,
        ).grid(row=0, column=0, padx=15, pady=(10, 0), sticky="w")

        tk.Label(
            header,
            text="鼠标自动点击器  |  作者: 王五一",
            font=("Segoe UI", 9),
            bg=self.HEADER_BG,
            fg=self.MUTED,
        ).grid(row=1, column=0, padx=15, pady=(0, 8), sticky="w")

        # Use a consistent padding
        pad = {"padx": 10, "pady": 5}

        # ── Section 1: Click Frequency ──────────────────────────────
        freq_frame = ttk.LabelFrame(self.root, text="点击频率设置", padding=10)
        freq_frame.grid(row=1, column=0, sticky="ew", **pad)
        freq_frame.columnconfigure(1, weight=1)

        self.freq_mode = tk.StringVar(value="preset")
        ttk.Radiobutton(
            freq_frame,
            text="内置频率",
            variable=self.freq_mode,
            value="preset",
            command=self._on_freq_mode_change,
        ).grid(row=0, column=0, sticky="w")

        self.preset_var = tk.StringVar(value="5 次/秒")
        self.preset_combo = ttk.Combobox(
            freq_frame,
            textvariable=self.preset_var,
            values=list(self.PRESET_FREQUENCIES.keys()),
            state="readonly",
            width=12,
        )
        self.preset_combo.grid(row=0, column=1, sticky="w", padx=(5, 0))
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_change)

        ttk.Radiobutton(
            freq_frame,
            text="自定义频率",
            variable=self.freq_mode,
            value="custom",
            command=self._on_freq_mode_change,
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))

        custom_inner = ttk.Frame(freq_frame)
        custom_inner.grid(row=1, column=1, sticky="w", padx=(5, 0), pady=(5, 0))

        self.custom_entry = ttk.Entry(custom_inner, width=8)
        self.custom_entry.grid(row=0, column=0)
        self.custom_entry.insert(0, "5")
        self.custom_entry.config(state="disabled")
        ttk.Label(custom_inner, text="次/秒").grid(row=0, column=1, padx=(3, 0))
        self.custom_apply_btn = ttk.Button(
            custom_inner,
            text="应用",
            width=5,
            state="disabled",
            command=self._apply_custom_freq,
        )
        self.custom_apply_btn.grid(row=0, column=2, padx=(5, 0))

        # ── Section 2: Background Mode ──────────────────────────────
        bg_frame = ttk.LabelFrame(self.root, text="后台模式", padding=10)
        bg_frame.grid(row=2, column=0, sticky="ew", **pad)

        self.bg_var = tk.BooleanVar(value=False)
        self.bg_check = ttk.Checkbutton(
            bg_frame,
            text="运行在后台（不影响用户鼠标使用）",
            variable=self.bg_var,
            command=self._on_bg_toggle,
        )
        self.bg_check.grid(row=0, column=0, sticky="w")

        self.bg_status_label = ttk.Label(
            bg_frame,
            text="后台模式关闭 — 点击将跟随鼠标位置",
            foreground="gray",
        )
        self.bg_status_label.grid(row=1, column=0, sticky="w", pady=(3, 0))

        ttk.Label(
            bg_frame,
            text=f"快捷键切换: {self.BG_TOGGLE_DISPLAY}",
            foreground=self.MUTED,
            font=("Segoe UI", 8),
        ).grid(row=2, column=0, sticky="w", pady=(2, 0))

        self.bg_pos_btn = ttk.Button(
            bg_frame,
            text="设置后台点击位置 (3 秒后记录鼠标位置)",
            command=self._record_bg_position,
            state="disabled",
        )
        self.bg_pos_btn.grid(row=3, column=0, sticky="w", pady=(5, 0))

        # ── Section 3: Auto Click Toggle ────────────────────────────
        toggle_frame = ttk.LabelFrame(self.root, text="自动点击", padding=10)
        toggle_frame.grid(row=3, column=0, sticky="ew", **pad)

        # Animated status dot
        self.status_canvas = tk.Canvas(
            toggle_frame,
            width=18,
            height=18,
            bg=self.BG_COLOR,
            highlightthickness=0,
        )
        self.status_canvas.grid(row=0, column=0, padx=(0, 5))
        self.status_dot = self.status_canvas.create_oval(
            3, 3, 15, 15, fill=self.DANGER, outline=""
        )

        self.status_var = tk.StringVar(value="已停止")
        self.toggle_btn = ttk.Button(
            toggle_frame,
            text="开启自动点击",
            command=self._toggle_clicking,
            style="Accent.TButton",
        )
        self.toggle_btn.grid(row=0, column=1)

        self.status_label = ttk.Label(
            toggle_frame,
            textvariable=self.status_var,
            foreground=self.DANGER,
            font=("", 11, "bold"),
        )
        self.status_label.grid(row=0, column=2, padx=(15, 0))

        # ── Section 4: Hotkey Settings ──────────────────────────────
        hotkey_frame = ttk.LabelFrame(self.root, text="快捷键设置", padding=10)
        hotkey_frame.grid(row=4, column=0, sticky="ew", **pad)

        self.hotkey_var = tk.StringVar(value=self.hotkey_display)
        ttk.Label(hotkey_frame, text="开启/关闭快捷键:").grid(
            row=0, column=0, sticky="w"
        )
        self.hotkey_entry = ttk.Entry(
            hotkey_frame, textvariable=self.hotkey_var, width=20, state="readonly"
        )
        self.hotkey_entry.grid(row=0, column=1, padx=(5, 0))

        self.record_hotkey_btn = ttk.Button(
            hotkey_frame, text="录制快捷键", command=self._start_hotkey_recording
        )
        self.record_hotkey_btn.grid(row=0, column=2, padx=(5, 0))

        # ── Section 5: Help ─────────────────────────────────────────
        help_frame = ttk.Frame(self.root, padding=5)
        help_frame.grid(row=5, column=0, sticky="ew", **pad)

        ttk.Button(help_frame, text="帮助", command=self._show_help).grid(
            row=0, column=0, sticky="e"
        )
        help_frame.columnconfigure(0, weight=1)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Frequency handling ──────────────────────────────────────────

    def _on_freq_mode_change(self):
        """Handle switching between preset and custom frequency modes."""
        if self.freq_mode.get() == "preset":
            self.preset_combo.config(state="readonly")
            self.custom_entry.config(state="disabled")
            self.custom_apply_btn.config(state="disabled")
            self._on_preset_change()
        else:
            self.preset_combo.config(state="disabled")
            self.custom_entry.config(state="normal")
            self.custom_apply_btn.config(state="normal")

    def _on_preset_change(self, _event=None):
        """Apply the selected preset frequency."""
        label = self.preset_var.get()
        self.frequency = self.PRESET_FREQUENCIES.get(label, 5)

    def _apply_custom_freq(self):
        """Validate and apply a custom frequency value."""
        raw = self.custom_entry.get().strip()
        try:
            value = int(raw)
            if value < 1 or value > 1000:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "无效输入", "请输入 1 到 1000 之间的整数作为每秒点击次数。"
            )
            return
        self.frequency = value
        messagebox.showinfo("已应用", f"自定义频率已设置为 {value} 次/秒。")

    # ── Background mode ─────────────────────────────────────────────

    def _on_bg_toggle(self):
        """Handle background mode checkbox toggle (real-time effect)."""
        with self._lock:
            self.background_mode = self.bg_var.get()
            bg_mode = self.background_mode
            bg_pos = self.background_position
        if bg_mode:
            self.bg_pos_btn.config(state="normal")
            if bg_pos:
                x, y = bg_pos
                self.bg_status_label.config(
                    text=f"后台模式开启 — 点击位置: ({x}, {y})",
                    foreground=self.SUCCESS,
                )
            else:
                self.bg_status_label.config(
                    text="后台模式开启 — 请先设置点击位置",
                    foreground=self.WARNING,
                )
        else:
            self.bg_pos_btn.config(state="disabled")
            self.bg_status_label.config(
                text="后台模式关闭 — 点击将跟随鼠标位置",
                foreground="gray",
            )

    def _toggle_bg_mode_from_hotkey(self):
        """Toggle background mode via the Ctrl+Alt+I hotkey."""
        new_val = not self.bg_var.get()
        self.bg_var.set(new_val)
        self._on_bg_toggle()

    def _record_bg_position(self):
        """Record the mouse position after a 3-second countdown."""
        self.bg_pos_btn.config(state="disabled")
        self._countdown(3)

    def _countdown(self, remaining):
        """Display a countdown then capture mouse position."""
        if remaining > 0:
            self.bg_status_label.config(
                text=f"将在 {remaining} 秒后记录鼠标位置…",
                foreground="blue",
            )
            self.root.after(1000, self._countdown, remaining - 1)
        else:
            pos = self.mouse.position
            with self._lock:
                self.background_position = pos
            self.bg_status_label.config(
                text=f"后台模式开启 — 点击位置: ({pos[0]}, {pos[1]})",
                foreground=self.SUCCESS,
            )
            self.bg_pos_btn.config(state="normal")

    # ── Auto-click toggling ─────────────────────────────────────────

    def _toggle_clicking(self):
        """Toggle auto-clicking on or off."""
        if self.clicking:
            self._stop_clicking()
        else:
            self._start_clicking()

    def _start_clicking(self):
        """Start the auto-click thread.

        In non-background mode the application window is minimized to prevent
        the auto-clicker from clicking on its own UI elements.  The window is
        restored automatically when clicking stops.
        """
        # Validate background mode has a position set
        with self._lock:
            bg_mode = self.background_mode
            bg_pos = self.background_position
        if bg_mode and bg_pos is None:
            messagebox.showwarning(
                "未设置位置",
                "后台模式已开启，但尚未设置点击位置。\n"
                "请先点击「设置后台点击位置」按钮。",
            )
            return

        self.clicking = True
        self._stop_event.clear()
        self.status_var.set("运行中")
        self.status_label.config(foreground=self.SUCCESS)
        self.toggle_btn.config(text="停止自动点击")

        # Start status dot animation
        self._pulse_step = 0
        self._animate_status()

        # In non-background mode, minimize the window so the auto-clicker
        # does not click on the application's own buttons (self-click freeze).
        if not bg_mode:
            self.root.iconify()

        self.click_thread = threading.Thread(target=self._click_loop, daemon=True)
        self.click_thread.start()

    def _stop_clicking(self):
        """Stop the auto-click thread and wait for it to finish."""
        self.clicking = False
        self._stop_event.set()  # wake the thread immediately

        # Wait for the click thread to finish so it is not mid-click when
        # we update the UI or destroy the window.
        if self.click_thread is not None and self.click_thread.is_alive():
            self.click_thread.join(timeout=2)
        self.click_thread = None

        # Stop status dot animation
        if self._animation_after_id is not None:
            self.root.after_cancel(self._animation_after_id)
            self._animation_after_id = None

        self.status_var.set("已停止")
        self.status_label.config(foreground=self.DANGER)
        self.status_canvas.itemconfig(self.status_dot, fill=self.DANGER)
        self.toggle_btn.config(text="开启自动点击")

        # Restore the window if it was minimized during non-bg clicking.
        self.root.deiconify()

    def _animate_status(self):
        """Animate the status dot with a pulsing green effect while clicking."""
        if not self.clicking:
            return
        self._pulse_step += 1
        # Smooth sine-wave pulse between darker and brighter green
        t = math.sin(self._pulse_step * 0.15) * 0.5 + 0.5
        g = int(130 + t * 125)  # green channel: 130–255
        color = f"#00{g:02x}40"
        self.status_canvas.itemconfig(self.status_dot, fill=color)
        self._animation_after_id = self.root.after(50, self._animate_status)

    def _click_loop(self):
        """Worker loop that performs mouse clicks at the configured frequency.

        Reads ``self.frequency`` each iteration so runtime changes take effect
        immediately.  If the frequency is somehow zero or negative the loop
        waits 1 second and re-checks rather than performing clicks.
        """
        try:
            self._click_loop_inner()
        except Exception:
            logger.exception(
                "Unexpected error in click loop (freq=%s, bg_mode=%s)",
                self.frequency,
                self.background_mode,
            )
            # Schedule UI reset on the main thread so the user sees "已停止"
            # instead of a stuck "运行中" status.
            self.clicking = False
            try:
                self.root.after(0, self._stop_clicking)
            except Exception:
                pass  # root may already be destroyed

    def _click_loop_inner(self):
        """Inner click loop separated for clean exception handling."""
        while self.clicking:
            freq = self.frequency
            if freq <= 0:
                # Invalid frequency — wait and re-check rather than clicking.
                if self._stop_event.wait(timeout=1.0):
                    break
                continue
            interval = max(1.0 / freq, _MIN_INTERVAL)
            with self._lock:
                bg_mode = self.background_mode
                bg_pos = self.background_position
            if bg_mode and bg_pos:
                self._bg_click_at_position(bg_pos[0], bg_pos[1])
            else:
                # Click at current cursor position
                self.mouse.click(Button.left)
            # Use Event.wait so _stop_clicking can cancel instantly
            if self._stop_event.wait(timeout=interval):
                break

    def _bg_click_at_position(self, x, y):
        """Perform a click at (x, y) with minimal disruption to the user's cursor.

        On Windows, uses batched Win32 ``SendInput`` API calls via ctypes so
        that the cursor move, click, and restore happen as fast as possible.
        On other platforms, falls back to pynput save/move/click/restore.
        """
        if sys.platform == "win32":
            self._bg_click_win32(x, y)
        else:
            original_pos = self.mouse.position
            self.mouse.position = (x, y)
            self.mouse.click(Button.left)
            self.mouse.position = original_pos

    @staticmethod
    def _bg_click_win32(x, y):
        """Windows background click using SendInput for minimal cursor disruption.

        Batches move-to-target, button-down, button-up, and move-back into a
        single ``SendInput`` call so the cursor displacement is as brief as
        possible.
        """
        MOUSEEVENTF_MOVE = 0x0001
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004
        MOUSEEVENTF_ABSOLUTE = 0x8000
        INPUT_MOUSE = 0

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class _INPUT_UNION(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("_union",)
            _fields_ = [
                ("type", ctypes.c_ulong),
                ("_union", _INPUT_UNION),
            ]

        # Current cursor position
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))

        # Screen size for absolute coordinate conversion
        scr_w = ctypes.windll.user32.GetSystemMetrics(0)
        scr_h = ctypes.windll.user32.GetSystemMetrics(1)

        def _to_abs(val, size):
            return int(val * 65536 / size)

        tgt_x = _to_abs(x, scr_w)
        tgt_y = _to_abs(y, scr_h)
        rst_x = _to_abs(pt.x, scr_w)
        rst_y = _to_abs(pt.y, scr_h)

        events = (INPUT * 4)()

        # 1. Move to target
        events[0].type = INPUT_MOUSE
        events[0].mi.dx = tgt_x
        events[0].mi.dy = tgt_y
        events[0].mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE

        # 2. Left button down
        events[1].type = INPUT_MOUSE
        events[1].mi.dwFlags = MOUSEEVENTF_LEFTDOWN

        # 3. Left button up
        events[2].type = INPUT_MOUSE
        events[2].mi.dwFlags = MOUSEEVENTF_LEFTUP

        # 4. Restore original position
        events[3].type = INPUT_MOUSE
        events[3].mi.dx = rst_x
        events[3].mi.dy = rst_y
        events[3].mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE

        ctypes.windll.user32.SendInput(
            4, ctypes.byref(events[0]), ctypes.sizeof(INPUT)
        )

    # ── Global keyboard listener ────────────────────────────────────

    def _start_keyboard_listener(self):
        """Start a global keyboard listener for hotkey detection.

        Uses ``pynput.keyboard.Listener`` directly (instead of
        ``GlobalHotKeys``) and manually tracks pressed keys so that hotkey
        detection is more reliable across different system configurations.
        """
        self._stop_keyboard_listener()
        self._keyboard_listener = KeyboardListener(
            on_press=self._on_global_key_press,
            on_release=self._on_global_key_release,
        )
        self._keyboard_listener.daemon = True
        self._keyboard_listener.start()

    def _stop_keyboard_listener(self):
        """Stop the global keyboard listener if active."""
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

    @staticmethod
    def _normalize_key(key):
        """Normalize a pynput key to a simple lowercase string for comparison."""
        if isinstance(key, Key):
            name = key.name
            if name.startswith("ctrl"):
                return "ctrl"
            if name.startswith("alt"):
                return "alt"
            if name.startswith("shift"):
                return "shift"
            if name.startswith("cmd"):
                return "cmd"
            return name
        if isinstance(key, KeyCode):
            if key.char is not None:
                return key.char.lower()
            # Virtual key codes 65–90 correspond to A–Z
            if key.vk is not None and 65 <= key.vk <= 90:
                return chr(key.vk).lower()
        return None

    def _on_global_key_press(self, key):
        """Track key press and check for hotkey matches."""
        normalized = self._normalize_key(key)
        if normalized is None:
            return
        self._pressed_keys.add(normalized)
        self._check_hotkeys()

    def _on_global_key_release(self, key):
        """Track key release and reset hotkey cooldowns."""
        normalized = self._normalize_key(key)
        if normalized is None:
            return
        self._pressed_keys.discard(normalized)
        # Any key release resets cooldowns so the combo can fire again
        self._hotkey_cooldown = False
        self._bg_hotkey_cooldown = False

    @staticmethod
    def _parse_hotkey(combo):
        """Parse a pynput-format hotkey string into a set of normalized keys.

        Example: ``"<ctrl>+<alt>+s"`` → ``{"ctrl", "alt", "s"}``
        """
        keys = set()
        for part in combo.split("+"):
            part = part.strip()
            if part.startswith("<") and part.endswith(">"):
                keys.add(part[1:-1].lower())
            else:
                keys.add(part.lower())
        return keys

    def _check_hotkeys(self):
        """Check if any registered hotkey combination is currently pressed."""
        # Toggle auto-clicking hotkey
        required = self._parse_hotkey(self.hotkey_combo)
        if required and required.issubset(self._pressed_keys):
            if not self._hotkey_cooldown:
                self._hotkey_cooldown = True
                self.root.after(0, self._toggle_clicking)

        # Ctrl+Alt+I — toggle background mode
        if self.BG_TOGGLE_HOTKEY.issubset(self._pressed_keys):
            if not self._bg_hotkey_cooldown:
                self._bg_hotkey_cooldown = True
                self.root.after(0, self._toggle_bg_mode_from_hotkey)

    def _start_hotkey_recording(self):
        """Enter hotkey recording mode — next key combo sets the new hotkey."""
        self.hotkey_var.set("请按下组合键…")
        self.record_hotkey_btn.config(state="disabled")
        self._recording_keys = set()
        self._recording_key_names = []
        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.bind("<KeyRelease>", self._on_key_release)

    def _on_key_press(self, event):
        """Capture keys during hotkey recording."""
        self._recording_keys.add(event.keycode)
        name = self._key_event_to_display(event)
        if name and name not in self._recording_key_names:
            self._recording_key_names.append(name)
        self.hotkey_var.set("+".join(self._recording_key_names))

    def _on_key_release(self, event):
        """Finalize hotkey when all keys are released."""
        self._recording_keys.discard(event.keycode)
        if not self._recording_keys and self._recording_key_names:
            self.root.unbind("<KeyPress>")
            self.root.unbind("<KeyRelease>")
            self.record_hotkey_btn.config(state="normal")

            display = "+".join(self._recording_key_names)
            pynput_combo = self._display_to_pynput(self._recording_key_names)

            self.hotkey_display = display
            self.hotkey_combo = pynput_combo
            self.hotkey_var.set(display)

    @staticmethod
    def _key_event_to_display(event):
        """Convert a tkinter key event to a human-readable key name."""
        mapping = {
            "Control_L": "Ctrl",
            "Control_R": "Ctrl",
            "Alt_L": "Alt",
            "Alt_R": "Alt",
            "Shift_L": "Shift",
            "Shift_R": "Shift",
            "Super_L": "Win",
            "Super_R": "Win",
        }
        keysym = event.keysym
        if keysym in mapping:
            return mapping[keysym]
        if len(keysym) == 1:
            return keysym.upper()
        return keysym

    @staticmethod
    def _display_to_pynput(names):
        """Convert a list of display key names to a pynput hotkey string."""
        pynput_map = {
            "Ctrl": "<ctrl>",
            "Alt": "<alt>",
            "Shift": "<shift>",
            "Win": "<cmd>",
        }
        parts = []
        for n in names:
            if n in pynput_map:
                parts.append(pynput_map[n])
            else:
                parts.append(n.lower())
        return "+".join(parts)

    # ── Help ────────────────────────────────────────────────────────

    @staticmethod
    def _show_help():
        """Display the help dialog."""
        help_text = (
            "【AutoMouseClick 使用帮助】\n\n"
            "1. 点击频率设置\n"
            "   • 内置频率：选择 5次/秒、10次/秒 或 20次/秒。\n"
            "   • 自定义频率：输入 1~1000 之间的整数并点击「应用」。\n\n"
            "2. 后台模式\n"
            "   • 勾选后，自动点击将在指定固定位置进行，\n"
            "     不会影响您当前的鼠标操作。\n"
            "   • 需要先点击「设置后台点击位置」，3 秒后\n"
            "     将记录鼠标当前位置作为点击目标。\n"
            "   • 可随时勾选/取消后台模式，实时切换。\n"
            "   • 快捷键 Ctrl+Alt+I 可快速开启/关闭后台模式。\n\n"
            "3. 自动点击\n"
            "   • 点击「开启自动点击」按钮或使用快捷键\n"
            "     来启动/停止自动点击。\n\n"
            "4. 快捷键设置\n"
            "   • 默认快捷键: Ctrl+Alt+S\n"
            "   • 点击「录制快捷键」后按下新的组合键即可更改。\n\n"
            "5. 快捷键一览\n"
            "   • Ctrl+Alt+S — 开启/关闭自动点击（可自定义）\n"
            "   • Ctrl+Alt+I — 开启/关闭后台模式\n\n"
            "6. 注意事项\n"
            "   • 非后台模式下，点击发生在鼠标当前位置。\n"
            "   • 关闭窗口将停止所有自动点击。\n\n"
            "作者: 王五一"
        )
        messagebox.showinfo("帮助", help_text)

    # ── Lifecycle ───────────────────────────────────────────────────

    def _on_close(self):
        """Clean up resources and close the application."""
        self._stop_clicking()
        self._stop_keyboard_listener()
        self.root.destroy()

    def run(self):
        """Start the application main loop."""
        self.root.mainloop()


if __name__ == "__main__":
    app = AutoMouseClick()
    app.run()
