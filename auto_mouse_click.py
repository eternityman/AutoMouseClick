"""AutoMouseClick - Desktop auto mouse click application.

A desktop application with a visual interface that provides automatic mouse
clicking at configurable frequencies, with support for background mode and
global hotkey toggling.
"""

import logging
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from pynput.keyboard import GlobalHotKeys
from pynput.mouse import Button, Controller

logger = logging.getLogger(__name__)


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

    def __init__(self):
        self.mouse = Controller()
        self.clicking = False
        self.click_thread = None
        self.hotkey_listener = None
        self._lock = threading.Lock()

        # Settings
        self.frequency = 5  # clicks per second
        self.background_mode = False
        self.background_position = None  # stored (x, y) for background mode

        # Current hotkey configuration
        self.hotkey_combo = self.DEFAULT_HOTKEY
        self.hotkey_display = self.DEFAULT_HOTKEY_DISPLAY

        self._build_ui()
        self._start_hotkey_listener()

    def _build_ui(self):
        """Build the main application window and all widgets."""
        self.root = tk.Tk()
        self.root.title("AutoMouseClick - 鼠标自动点击器")
        self.root.resizable(False, False)

        # Use a consistent padding
        pad = {"padx": 10, "pady": 5}

        # ── Section 1: Click Frequency ──────────────────────────────
        freq_frame = ttk.LabelFrame(self.root, text="点击频率设置", padding=10)
        freq_frame.grid(row=0, column=0, sticky="ew", **pad)
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

        self.custom_entry = ttk.Entry(custom_inner, width=8, state="disabled")
        self.custom_entry.grid(row=0, column=0)
        self.custom_entry.insert(0, "5")
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
        bg_frame.grid(row=1, column=0, sticky="ew", **pad)

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

        self.bg_pos_btn = ttk.Button(
            bg_frame,
            text="设置后台点击位置 (3 秒后记录鼠标位置)",
            command=self._record_bg_position,
            state="disabled",
        )
        self.bg_pos_btn.grid(row=2, column=0, sticky="w", pady=(5, 0))

        # ── Section 3: Auto Click Toggle ────────────────────────────
        toggle_frame = ttk.LabelFrame(self.root, text="自动点击", padding=10)
        toggle_frame.grid(row=2, column=0, sticky="ew", **pad)

        self.status_var = tk.StringVar(value="已停止")
        self.toggle_btn = ttk.Button(
            toggle_frame, text="开启自动点击", command=self._toggle_clicking
        )
        self.toggle_btn.grid(row=0, column=0)

        self.status_label = ttk.Label(
            toggle_frame,
            textvariable=self.status_var,
            foreground="red",
            font=("", 11, "bold"),
        )
        self.status_label.grid(row=0, column=1, padx=(15, 0))

        # ── Section 4: Hotkey Settings ──────────────────────────────
        hotkey_frame = ttk.LabelFrame(self.root, text="快捷键设置", padding=10)
        hotkey_frame.grid(row=3, column=0, sticky="ew", **pad)

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
        help_frame.grid(row=4, column=0, sticky="ew", **pad)

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
                    foreground="green",
                )
            else:
                self.bg_status_label.config(
                    text="后台模式开启 — 请先设置点击位置",
                    foreground="orange",
                )
        else:
            self.bg_pos_btn.config(state="disabled")
            self.bg_status_label.config(
                text="后台模式关闭 — 点击将跟随鼠标位置",
                foreground="gray",
            )

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
                foreground="green",
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
        """Start the auto-click thread."""
        # Validate background mode has a position set
        if self.background_mode and self.background_position is None:
            messagebox.showwarning(
                "未设置位置",
                "后台模式已开启，但尚未设置点击位置。\n"
                "请先点击「设置后台点击位置」按钮。",
            )
            return

        self.clicking = True
        self.status_var.set("运行中")
        self.status_label.config(foreground="green")
        self.toggle_btn.config(text="停止自动点击")
        self.click_thread = threading.Thread(target=self._click_loop, daemon=True)
        self.click_thread.start()

    def _stop_clicking(self):
        """Stop the auto-click thread."""
        self.clicking = False
        self.status_var.set("已停止")
        self.status_label.config(foreground="red")
        self.toggle_btn.config(text="开启自动点击")

    def _click_loop(self):
        """Worker loop that performs mouse clicks at the configured frequency."""
        while self.clicking:
            interval = 1.0 / self.frequency
            with self._lock:
                bg_mode = self.background_mode
                bg_pos = self.background_position
            if bg_mode and bg_pos:
                # Save current position, move, click, restore
                original_pos = self.mouse.position
                self.mouse.position = bg_pos
                self.mouse.click(Button.left)
                self.mouse.position = original_pos
            else:
                # Click at current cursor position
                self.mouse.click(Button.left)
            time.sleep(interval)

    # ── Hotkey management ───────────────────────────────────────────

    def _start_hotkey_listener(self):
        """Start a global hotkey listener with the current hotkey combo."""
        self._stop_hotkey_listener()
        try:
            self.hotkey_listener = GlobalHotKeys(
                {self.hotkey_combo: self._hotkey_triggered}
            )
            self.hotkey_listener.daemon = True
            self.hotkey_listener.start()
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("Failed to register hotkey '%s': %s", self.hotkey_combo, exc)

    def _stop_hotkey_listener(self):
        """Stop the current global hotkey listener if active."""
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
            self.hotkey_listener = None

    def _hotkey_triggered(self):
        """Called from the hotkey listener thread — schedule toggle on main thread."""
        self.root.after(0, self._toggle_clicking)

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

            self._start_hotkey_listener()

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
            "   • 可随时勾选/取消后台模式，实时切换。\n\n"
            "3. 自动点击\n"
            "   • 点击「开启自动点击」按钮或使用快捷键\n"
            "     来启动/停止自动点击。\n\n"
            "4. 快捷键设置\n"
            "   • 默认快捷键: Ctrl+Alt+S\n"
            "   • 点击「录制快捷键」后按下新的组合键即可更改。\n\n"
            "5. 注意事项\n"
            "   • 非后台模式下，点击发生在鼠标当前位置。\n"
            "   • 关闭窗口将停止所有自动点击。"
        )
        messagebox.showinfo("帮助", help_text)

    # ── Lifecycle ───────────────────────────────────────────────────

    def _on_close(self):
        """Clean up resources and close the application."""
        self._stop_clicking()
        self._stop_hotkey_listener()
        self.root.destroy()

    def run(self):
        """Start the application main loop."""
        self.root.mainloop()


if __name__ == "__main__":
    app = AutoMouseClick()
    app.run()
