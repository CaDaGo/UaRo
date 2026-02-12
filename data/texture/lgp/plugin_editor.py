#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os

# Optional imports for pipette
try:
    from pynput import mouse
    import pyscreenshot
    PIPETTE_AVAILABLE = True
except Exception:
    PIPETTE_AVAILABLE = False

from tkcolorpicker import askcolor

# ------------------------------------------------------------
# Color conversion helpers
# ------------------------------------------------------------

def ini_to_tk(color):
    """Convert 0xAARRGGBB → #RRGGBB"""
    if not color or not color.startswith("0x") or len(color) != 10:
        return "#FFFFFF"
    hexpart = color[4:]  # skip 0xAA → take RR GG BB
    return "#" + hexpart.lower()

def tk_to_ini(hexcolor, old_ini_color):
    """Convert #RRGGBB → 0xAARRGGBB (keep old alpha if possible)"""
    if not hexcolor:
        return old_ini_color
    hexcolor = hexcolor.replace("#", "")
    alpha = old_ini_color[2:4] if old_ini_color and old_ini_color.startswith("0x") else "FF"
    return "0x" + alpha + hexcolor.upper()

def rgb_to_ini(r, g, b, old_ini_color=None):
    """Convert (r,g,b) → 0xAARRGGBB (keep alpha if possible)"""
    alpha = "FF"
    if old_ini_color and old_ini_color.startswith("0x") and len(old_ini_color) == 10:
        alpha = old_ini_color[2:4]
    return "0x" + alpha + f"{r:02X}{g:02X}{b:02X}"

# ------------------------------------------------------------
# Parsing
# ------------------------------------------------------------

def parse_ini(text):
    lines = text.splitlines()
    skills = {}
    section = None
    last_comment = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            last_comment = None
            continue

        if stripped.startswith(";"):
            last_comment = line
            continue

        if "=" in stripped:
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip()

            if key.startswith("Skill") and len(key) == 9:
                if key not in skills:
                    skills[key] = {"comment": None, "image": None, "color": None}

                if section == "LGP::CELL_COLOR":
                    skills[key]["color"] = value
                    if last_comment:
                        skills[key]["comment"] = last_comment
                        last_comment = None

                if section == "LGP::CELL_IMAGE":
                    skills[key]["image"] = value

    return lines, skills


def apply_filename_rules(skills):
    for sid, data in skills.items():
        if not data["image"]:
            comment = data["comment"]
            if comment and "#" in comment:
                name = comment.split("#", 1)[1].strip()
                data["image"] = name.lower() + ".bmp"
            else:
                data["image"] = sid.lower() + ".bmp"


# ------------------------------------------------------------
# Rebuild INI
# ------------------------------------------------------------

def rebuild_ini(lines, skills):
    new_lines = []
    section = None
    i = 0
    n = len(lines)
    skill_ids = sorted(skills.keys())

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]

            if section == "LGP::CELL_IMAGE":
                new_lines.append(line)
                i += 1
                while i < n:
                    t = lines[i].strip()
                    if t.startswith("[") and t.endswith("]"):
                        break
                    i += 1

                for sid in skill_ids:
                    data = skills[sid]
                    if data["comment"]:
                        new_lines.append(data["comment"])
                    new_lines.append(f"{sid} = {data['image']}")
                    new_lines.append("")
                continue

            if section == "LGP::CELL_COLOR":
                new_lines.append(line)
                i += 1
                while i < n:
                    t = lines[i].strip()
                    if t.startswith("[") and t.endswith("]"):
                        break
                    i += 1

                for sid in skill_ids:
                    data = skills[sid]
                    if data["color"]:
                        if data["comment"]:
                            new_lines.append(data["comment"])
                        new_lines.append(f"{sid}={data['color']}")
                        new_lines.append("")
                continue

        new_lines.append(line)
        i += 1

    return "\n".join(new_lines) + "\n"


# ------------------------------------------------------------
# GUI
# ------------------------------------------------------------

class PluginEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("plugin.ini Editor")

        self.file_path = None
        self.original_lines = []
        self.skills = {}

        self.build_ui()

        if not PIPETTE_AVAILABLE:
            self.root.after(500, self.show_pipette_warning)

    def show_pipette_warning(self):
        messagebox.showinfo(
            "Pipette not available",
            "Pipette requires 'pynput' and 'pyscreenshot'.\n\n"
            "Install them in your venv:\n"
            "  pip install pynput pyscreenshot"
        )

    def build_ui(self):
        frame = tk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        load_btn = tk.Button(frame, text="Open plugin.ini", command=self.load_ini)
        load_btn.pack(anchor="w")

        # Treeview with Preview + Pipette columns
        self.tree = ttk.Treeview(
            frame,
            columns=("comment", "image", "color", "preview", "pipette"),
            show="headings"
        )
        self.tree.heading("comment", text="Comment")
        self.tree.heading("image", text="Image")
        self.tree.heading("color", text="Color")
        self.tree.heading("preview", text="Preview")
        self.tree.heading("pipette", text="Pipette")

        self.tree.column("comment", width=260, anchor="w")
        self.tree.column("image", width=140, anchor="w")
        self.tree.column("color", width=110, anchor="w")
        self.tree.column("preview", width=80, anchor="center")
        self.tree.column("pipette", width=70, anchor="center")

        self.tree.pack(fill="both", expand=True, pady=10)

        # Click handling
        self.tree.bind("<Button-1>", self.on_tree_click)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill="x")

        tk.Button(btn_frame, text="Edit Selected", command=self.edit_selected).pack(side="left")
        tk.Button(btn_frame, text="Save plugin.ini", command=self.save_ini).pack(side="right")

    def load_ini(self):
        path = filedialog.askopenfilename(filetypes=[("INI files", "*.ini")])
        if not path:
            return

        self.file_path = path

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        self.original_lines, self.skills = parse_ini(text)
        apply_filename_rules(self.skills)

        self.refresh_table()

    def make_preview_text(self, color):
        # simple block swatch using text
        if not color or not color.startswith("0x") or len(color) != 10:
            return ""
        return "██"

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for sid in sorted(self.skills.keys()):
            data = self.skills[sid]
            comment = data["comment"] or ""
            image = data["image"] or ""
            color = data["color"] or ""
            preview = self.make_preview_text(color)
            self.tree.insert(
                "",
                "end",
                iid=sid,
                values=(comment, image, color, preview, "🎯")
            )

    # --------------------------------------------------------
    # Inline pipette + preview in the main table
    # --------------------------------------------------------
    def on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        # columns are "#1".."#5"
        if column == "#4":  # Preview column -> open color picker
            self.open_color_picker_for_row(row_id)
        elif column == "#5":  # Pipette column
            self.start_pipette_for_row(row_id)

    def open_color_picker_for_row(self, sid):
        data = self.skills.get(sid)
        if not data:
            return
        tk_color = ini_to_tk(data["color"])
        rgb, hexcolor = askcolor(color=tk_color)
        if hexcolor:
            data["color"] = tk_to_ini(hexcolor, data["color"])
            self.tree.set(sid, "color", data["color"])
            self.tree.set(sid, "preview", self.make_preview_text(data["color"]))

    def start_pipette_for_row(self, sid):
        if not PIPETTE_AVAILABLE:
            messagebox.showinfo(
                "Pipette not available",
                "Pipette requires 'pynput' and 'pyscreenshot'.\n\n"
                "Install them in your venv:\n"
                "  pip install pynput pyscreenshot"
            )
            return

        data = self.skills.get(sid)
        if not data:
            return

        # Hide window
        try:
            self.root.withdraw()
        except Exception:
            pass

        pipette_state = {"listener": None}

        def safe_restore():
            try:
                self.root.deiconify()
            except Exception:
                pass

        def on_move(x, y):
            try:
                img = pyscreenshot.grab(bbox=(x, y, x+3, y+3))
                r, g, b = img.getpixel((1, 1))
                new_color = rgb_to_ini(r, g, b, data["color"])
                data["color"] = new_color
                self.tree.set(sid, "color", new_color)
                self.tree.set(sid, "preview", self.make_preview_text(new_color))
            except Exception:
                return True

        def on_click(x, y, button, pressed):
            try:
                if pressed:
                    return
                if pipette_state["listener"]:
                    pipette_state["listener"].stop()
                    pipette_state["listener"] = None
                safe_restore()
                return False
            except Exception:
                safe_restore()
                return False

        def on_press(key):
            try:
                from pynput.keyboard import Key
                if key == Key.esc:
                    if pipette_state["listener"]:
                        pipette_state["listener"].stop()
                        pipette_state["listener"] = None
                    safe_restore()
                    return False
            except Exception:
                safe_restore()
                return False

        from pynput import keyboard

        try:
            m_listener = mouse.Listener(on_move=on_move, on_click=on_click)
            k_listener = keyboard.Listener(on_press=on_press)

            pipette_state["listener"] = m_listener

            m_listener.start()
            k_listener.start()
        except Exception:
            safe_restore()

    # --------------------------------------------------------
    # Edit window (with swatch + pipette + picker)
    # --------------------------------------------------------
    def edit_selected(self):
        sid = self.tree.focus()
        if not sid:
            messagebox.showwarning("No selection", "Select a skill first.")
            return

        data = self.skills[sid]

        win = tk.Toplevel(self.root)
        win.title(f"Edit {sid}")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="Image filename:").pack(anchor="w")
        img_entry = tk.Entry(win)
        img_entry.insert(0, data["image"])
        img_entry.pack(fill="x")

        color_frame = tk.Frame(win)
        color_frame.pack(fill="x", pady=5)

        tk.Label(color_frame, text="Color (0xAARRGGBB):").grid(row=0, column=0, sticky="w")

        color_entry = tk.Entry(color_frame, width=18)
        color_entry.insert(0, data["color"])
        color_entry.grid(row=0, column=1, padx=(5, 5))

        # Color swatch
        swatch = tk.Label(color_frame, width=4, relief="sunken")
        swatch.grid(row=0, column=2, padx=(5, 5))

        def update_swatch_from_ini():
            c = data["color"]
            tk_color = ini_to_tk(c)
            swatch.config(bg=tk_color)

        update_swatch_from_ini()

        # Pipette button (🎯)
        pipette_btn = tk.Button(color_frame, text="🎯", width=3)
        pipette_btn.grid(row=0, column=3, padx=(5, 0))

        # Pick Color button (tkcolorpicker)
        pick_btn = tk.Button(win, text="Pick Color", width=12)
        pick_btn.pack(pady=5)

        # --- Color picker logic ---
        def pick_color():
            tk_color = ini_to_tk(data["color"])
            rgb, hexcolor = askcolor(color=tk_color)
            if hexcolor:
                data["color"] = tk_to_ini(hexcolor, data["color"])
                color_entry.delete(0, tk.END)
                color_entry.insert(0, data["color"])
                update_swatch_from_ini()
                self.tree.set(sid, "color", data["color"])
                self.tree.set(sid, "preview", self.make_preview_text(data["color"]))

        pick_btn.config(command=pick_color)

        # --- Pipette logic (hover, click to confirm) ---
        pipette_listener = {"listener": None}

        def start_pipette_popup():
            if not PIPETTE_AVAILABLE:
                messagebox.showinfo(
                    "Pipette not available",
                    "Pipette requires 'pynput' and 'pyscreenshot'.\n\n"
                    "Install them in your venv:\n"
                    "  pip install pynput pyscreenshot"
                )
                return

            try:
                win.withdraw()
                self.root.withdraw()
            except Exception:
                pass

            def safe_restore_popup():
                try:
                    self.root.deiconify()
                    win.deiconify()
                except Exception:
                    pass

            def on_move(x, y):
                try:
                    img = pyscreenshot.grab(bbox=(x, y, x+3, y+3))
                    r, g, b = img.getpixel((1, 1))
                    new_color = rgb_to_ini(r, g, b, data["color"])
                    data["color"] = new_color
                    color_entry.delete(0, tk.END)
                    color_entry.insert(0, new_color)
                    update_swatch_from_ini()
                    self.tree.set(sid, "color", new_color)
                    self.tree.set(sid, "preview", self.make_preview_text(new_color))
                except Exception:
                    return True

            def on_click(x, y, button, pressed):
                try:
                    if pressed:
                        return
                    if pipette_listener["listener"]:
                        pipette_listener["listener"].stop()
                        pipette_listener["listener"] = None
                    safe_restore_popup()
                    return False
                except Exception:
                    safe_restore_popup()
                    return False

            def on_press(key):
                try:
                    from pynput.keyboard import Key
                    if key == Key.esc:
                        if pipette_listener["listener"]:
                            pipette_listener["listener"].stop()
                            pipette_listener["listener"] = None
                        safe_restore_popup()
                        return False
                except Exception:
                    safe_restore_popup()
                    return False

            from pynput import keyboard

            try:
                m_listener = mouse.Listener(on_move=on_move, on_click=on_click)
                k_listener = keyboard.Listener(on_press=on_press)

                pipette_listener["listener"] = m_listener

                m_listener.start()
                k_listener.start()
            except Exception:
                safe_restore_popup()

        pipette_btn.config(command=start_pipette_popup)

        def save_changes():
            data["image"] = img_entry.get().strip()
            data["color"] = color_entry.get().strip()
            self.refresh_table()
            win.destroy()

        tk.Button(win, text="Save", command=save_changes).pack(pady=10)

    def save_ini(self):
        if not self.file_path:
            return

        new_text = rebuild_ini(self.original_lines, self.skills)

        backup = self.file_path + ".bak"
        if not os.path.exists(backup):
            with open(backup, "w", encoding="utf-8") as f:
                f.write("\n".join(self.original_lines))

        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write(new_text)

        messagebox.showinfo("Saved", "plugin.ini updated successfully.")


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = PluginEditor(root)
    root.mainloop()

