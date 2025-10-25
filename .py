 import tkinter as tk
from tkinter import ttk, messagebox
import json, os, datetime, uuid

DATA_FILE = "productivity_hub_data.json"

# ---------------- Data model ----------------
# Task: {id, name, category, priority, due, done, pomodoros}
tasks = []
stats = {"total_pomodoros": 0, "daily_streaks": {}}  # {YYYY-MM-DD: count}
CATEGORIES = ["School", "Chores", "Health", "Work", "Personal"]
PRIORITIES = ["High", "Medium", "Low"]
PRIORITY_ORDER = {"High": 1, "Medium": 2, "Low": 3}

# ---------------- Persistence ----------------
def load_data():
    global tasks, stats
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            tasks = data.get("tasks", [])
            stats = data.get("stats", {"total_pomodoros": 0, "daily_streaks": {}})
        except Exception as e:
            print("Load error:", e)

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({"tasks": tasks, "stats": stats}, f, indent=2)
    except Exception as e:
        print("Save error:", e)

# ---------------- Helpers ----------------
def today_str():
    return datetime.date.today().strftime("%Y-%m-%d")

def parse_date(s):
    if not s:
        return None
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None

def format_due(s):
    return s if s else "No deadline"

def sort_tasks(task_list):
    today = datetime.date.today()
    far_future = today + datetime.timedelta(days=9999)
    def key(t):
        d = parse_date(t.get("due", "")) or far_future
        p = PRIORITY_ORDER.get(t.get("priority", "Medium"), 3)
        return (t.get("done", False), d, p)
    return sorted(task_list, key=key)

def count_overdue():
    today = datetime.date.today()
    return sum(
        1 for t in tasks
        if not t.get("done", False) and parse_date(t.get("due", "")) and parse_date(t.get("due", "")) < today
    )

def suggest_task_obj():
    pending = [t for t in tasks if not t.get("done", False)]
    if not pending:
        return None
    hour = datetime.datetime.now().hour
    # Heuristic category bonuses by time of day
    if 6 <= hour < 12:
        cat_bonus = {"School": -0.5, "Work": -0.5}
    elif 12 <= hour < 18:
        cat_bonus = {"Chores": -0.5, "Personal": -0.3}
    else:
        cat_bonus = {"Health": -0.5, "Personal": -0.3}
    today = datetime.date.today()
    def score(t):
        d = parse_date(t.get("due", ""))
        due_days = (d - today).days if d else 9999
        prio = PRIORITY_ORDER.get(t.get("priority", "Medium"), 3)
        return (due_days if due_days >= 0 else -100) + prio + cat_bonus.get(t.get("category", ""), 0)
    return sorted(pending, key=score)[0]

# ---------------- Dialogs ----------------
class TaskDialog(tk.Toplevel):
    def __init__(self, parent, title, task=None):
        super().__init__(parent)
        self.parent = parent
        self.title(title)
        self.resizable(False, False)
        self.task = task

        ttk.Label(self, text="Task name").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        self.name_entry = ttk.Entry(self, width=32)
        self.name_entry.grid(row=0, column=1, padx=8, pady=6)

        ttk.Label(self, text="Category").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        self.cat_var = tk.StringVar(value=CATEGORIES[0])
        self.cat_combo = ttk.Combobox(self, textvariable=self.cat_var, values=CATEGORIES, state="readonly", width=30)
        self.cat_combo.grid(row=1, column=1, padx=8, pady=6)

        ttk.Label(self, text="Priority").grid(row=2, column=0, padx=8, pady=6, sticky="e")
        self.prio_var = tk.StringVar(value="Medium")
        self.prio_combo = ttk.Combobox(self, textvariable=self.prio_var, values=PRIORITIES, state="readonly", width=30)
        self.prio_combo.grid(row=2, column=1, padx=8, pady=6)

        ttk.Label(self, text="Due date (YYYY-MM-DD)").grid(row=3, column=0, padx=8, pady=6, sticky="e")
        self.due_entry = ttk.Entry(self, width=32)
        self.due_entry.grid(row=3, column=1, padx=8, pady=6)

        btns = ttk.Frame(self)
        btns.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(btns, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=6)
        ttk.Button(btns, text="OK", command=self.on_ok).grid(row=0, column=1, padx=6)

        if self.task:
            self.name_entry.insert(0, self.task.get("name", ""))
            self.cat_var.set(self.task.get("category", CATEGORIES[0]))
            self.prio_var.set(self.task.get("priority", "Medium"))
            self.due_entry.insert(0, self.task.get("due", ""))

        self.transient(parent)
        self.grab_set()
        self.name_entry.focus()

    def on_ok(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Input", "Task name cannot be empty.")
            return
        category = self.cat_var.get().strip() or "Personal"
        priority = self.prio_var.get().strip() or "Medium"
        due = self.due_entry.get().strip()
        if due and parse_date(due) is None:
            messagebox.showwarning("Date", "Use YYYY-MM-DD or leave blank.")
            return

        if category not in CATEGORIES:
            CATEGORIES.append(category)
            self.parent.update_category_sources()

        if self.task is None:
            new_task = {
                "id": str(uuid.uuid4()),
                "name": name,
                "category": category,
                "priority": priority,
                "due": due,
                "done": False,
                "pomodoros": 0
            }
            tasks.append(new_task)
        else:
            self.task.update({
                "name": name,
                "category": category,
                "priority": priority,
                "due": due
            })
        save_data()
        self.parent.refresh_tasks()
        self.parent.refresh_study_combo()
        self.destroy()

# ---------------- Main app ----------------
class ProductivityApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Productivity Hub")
        self.geometry("900x600")
        self.resizable(False, False)
        load_data()
        self.create_ui()

        # Study tab state
        self.timer_running = False
        self.phase = "Idle"
        self.remaining = 0
        self.work_seconds = 0
        self.break_seconds = 0
        self.current_task = ""

    def create_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.tasks_tab = ttk.Frame(nb)
        self.study_tab = ttk.Frame(nb)
        self.summary_tab = ttk.Frame(nb)
        nb.add(self.tasks_tab, text="Tasks")
        nb.add(self.study_tab, text="Study (Pomodoro)")
        nb.add(self.summary_tab, text="Summary")

        self.build_tasks_tab()
        self.build_study_tab()
        self.build_summary_tab()

    # -------- Tasks tab --------
    def build_tasks_tab(self):
        top = ttk.Frame(self.tasks_tab)
        top.pack(fill="x", padx=6, pady=6)

        ttk.Button(top, text="Add Task", command=self.add_task).pack(side="left", padx=4)
        ttk.Button(top, text="Edit Selected", command=self.edit_task).pack(side="left", padx=4)
        ttk.Button(top, text="Delete Selected", command=self.delete_task).pack(side="left", padx=4)
        ttk.Button(top, text="Mark Done", command=self.mark_done).pack(side="left", padx=4)
        ttk.Button(top, text="Undo Done", command=self.undo_done).pack(side="left", padx=4)
        ttk.Button(top, text="Suggest Next", command=self.suggest_next).pack(side="left", padx=4)
        ttk.Button(top, text="Refresh", command=self.refresh_tasks).pack(side="right", padx=4)

        columns = ("name", "category", "priority", "due", "done", "pomodoros")
        self.tree = ttk.Treeview(self.tasks_tab, columns=columns, show="headings", height=18)
        for col, width in zip(columns, (260, 120, 90, 110, 70, 90)):
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<Double-1>", self.toggle_done)

        scroll = ttk.Scrollbar(self.tasks_tab, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.place(relx=1.0, rely=0.16, relheight=0.78, anchor="ne")

        self.refresh_tasks()

    def refresh_tasks(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for t in sort_tasks(tasks):
            self.tree.insert("", "end", iid=t["id"], values=(
                t["name"],
                t["category"],
                t["priority"],
                format_due(t["due"]),
                "✓" if t["done"] else "✗",
                t.get("pomodoros", 0)
            ))

    def get_selected_task(self):
        sel = self.tree.selection()
        if not sel:
            return None
        tid = sel[0]
        for t in tasks:
            if t["id"] == tid:
                return t
        return None

    def add_task(self):
        TaskDialog(self, "Add Task")

    def edit_task(self):
        t = self.get_selected_task()
        if not t:
            messagebox.showwarning("Select", "Pick a task to edit.")
            return
        TaskDialog(self, "Edit Task", task=t)

    def delete_task(self):
        t = self.get_selected_task()
        if not t:
            messagebox.showwarning("Select", "Pick a task to delete.")
            return
        if messagebox.askyesno("Confirm", f"Delete '{t['name']}'?"):
            tasks.remove(t)
            save_data()
            self.refresh_tasks()
            self.refresh_study_combo()

    def mark_done(self):
        t = self.get_selected_task()
        if not t:
            messagebox.showwarning("Select", "Pick a task to mark done.")
            return
        t["done"] = True
        save_data()
        self.refresh_tasks()
        self.refresh_study_combo()

    def undo_done(self):
        t = self.get_selected_task()
        if not t:
            messagebox.showwarning("Select", "Pick a task to undo.")
            return
        if not t["done"]:
            messagebox.showinfo("Undo", "That task is already pending.")
            return
        t["done"] = False
        save_data()
        self.refresh_tasks()
        self.refresh_study_combo()

    def toggle_done(self, event):
        t = self.get_selected_task()
        if not t:
            return
        t["done"] = not t.get("done", False)
        save_data()
        self.refresh_tasks()
        self.refresh_study_combo()

    def suggest_next(self):
        best = suggest_task_obj()
        if not best:
            messagebox.showinfo("Suggest", "No pending tasks. 🎉")
            return
        messagebox.showinfo(
            "Suggest",
            f"Next Task:\n{best['name']}\nCategory: {best['category']}\n"
            f"Priority: {best['priority']}\nDue: {format_due(best['due'])}"
        )

    def update_category_sources(self):
        # Placeholder for future expansion (e.g., category menus)
        pass

    # -------- Study tab --------
    def build_study_tab(self):
        top = ttk.Frame(self.study_tab)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Select task").grid(row=0, column=0, sticky="e", padx=4)
        self.study_var = tk.StringVar()
        self.study_combo = ttk.Combobox(top, textvariable=self.study_var, state="readonly", width=40)
        self.study_combo.grid(row=0, column=1, padx=4)
        ttk.Button(top, text="Refresh tasks", command=self.refresh_study_combo).grid(row=0, column=2, padx=4)

        ttk.Label(top, text="Work minutes").grid(row=1, column=0, sticky="e", padx=4)
        ttk.Label(top, text="Break minutes").grid(row=2, column=0, sticky="e", padx=4)
        self.work_entry = ttk.Entry(top, width=8)
        self.break_entry = ttk.Entry(top, width=8)
        self.work_entry.insert(0, "25")
        self.break_entry.insert(0, "5")
        self.work_entry.grid(row=1, column=1, sticky="w")
        self.break_entry.grid(row=2, column=1, sticky="w")

        mid = ttk.Frame(self.study_tab)
        mid.pack(fill="x", padx=8, pady=8)
        self.timer_label = ttk.Label(mid, text="Timer: 00:00", font=("Helvetica", 16))
        self.timer_label.pack(pady=4)

        btns = ttk.Frame(self.study_tab)
        btns.pack(pady=6)
        ttk.Button(btns, text="Start Pomodoro", command=self.start_pomodoro).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Stop", command=self.stop_pomodoro).grid(row=0, column=1, padx=4)

        self.refresh_study_combo()

    def refresh_study_combo(self):
        pending = [t["name"] for t in tasks if not t.get("done", False)]
        self.study_combo.configure(values=pending)
        if pending:
            self.study_var.set(pending[0])
        else:
            self.study_var.set("")

    # Fixed single-loop timer with auto break and no overlap
    def start_pomodoro(self):
        # Stop any existing timer cleanly
        if self.timer_running:
            self.stop_pomodoro()
        task_name = self.study_var.get()
        if not task_name:
            messagebox.showwarning("Select", "Pick a task to focus on.")
            return
        try:
            self.work_seconds = int(self.work_entry.get() or "25") * 60
            self.break_seconds = int(self.break_entry.get() or "5") * 60
        except ValueError:
            messagebox.showwarning("Input", "Enter integer minutes for work/break.")
            return

        self.current_task = task_name
        self.phase = "Work"
        self.remaining = self.work_seconds
        self.timer_running = True
        self.update_timer()

    def update_timer(self):
        if not self.timer_running:
            return
        mins, secs = divmod(self.remaining, 60)
        self.timer_label.config(text=f"{self.phase}: {mins:02d}:{secs:02d}")
        if self.remaining > 0:
            self.remaining -= 1
            self.after(1000, self.update_timer)
        else:
            if self.phase == "Work":
                messagebox.showinfo("Pomodoro", "Work block complete! Break starting.")
                self.phase = "Break"
                self.remaining = self.break_seconds
                self.update_timer()  # continue into break
            else:
                messagebox.showinfo("Pomodoro", "Break complete! Session logged.")
                # Log stats
                for t in tasks:
                    if t["name"] == self.current_task:
                        t["pomodoros"] = t.get("pomodoros", 0) + 1
                        break
                stats["total_pomodoros"] += 1
                day = today_str()
                stats["daily_streaks"][day] = stats["daily_streaks"].get(day, 0) + 1
                save_data()
                self.refresh_tasks()
                # Reset timer state
                self.timer_running = False
                self.phase = "Idle"
                self.remaining = 0
                self.timer_label.config(text="Timer: 00:00")

    def stop_pomodoro(self):
        self.timer_running = False
        self.phase = "Idle"
        self.remaining = 0
        self.timer_label.config(text="Timer stopped")

    # -------- Summary tab --------
    def build_summary_tab(self):
        top = ttk.Frame(self.summary_tab)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Refresh Summary", command=self.refresh_summary).pack(side="left", padx=4)
        ttk.Button(top, text="Suggest Next", command=self.suggest_next_from_summary).pack(side="left", padx=4)

        self.summary_text = tk.Text(self.summary_tab, height=20, width=100, state="disabled")
        self.summary_text.pack(fill="both", expand=True, padx=8, pady=8)

        self.refresh_summary()

    def refresh_summary(self):
        total = len(tasks)
        done = sum(1 for t in tasks if t.get("done", False))
        pending = total - done
        overdue = count_overdue()
        total_poms = stats.get("total_pomodoros", 0)

        today = datetime.date.today()
        last7 = []
        for i in range(7):
            d = (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            last7.append(f"{d}: {stats['daily_streaks'].get(d, 0)}")

        lines = [
            "--- Summary ---",
            f"Total tasks: {total}",
            f"Completed tasks: {done}",
            f"Pending tasks: {pending}",
            f"Overdue tasks: {overdue}",
            f"Total pomodoros: {total_poms}",
            "Last 7 days pomodoros:",
            *last7[::-1],
            "",
            "Top pending tasks:",
        ]
        for t in sort_tasks([x for x in tasks if not x.get("done", False)])[:5]:
            lines.append(f"- {t['name']} | {t['category']} | {t['priority']} | due {format_due(t['due'])} | pomodoros {t.get('pomodoros',0)}")

        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert("1.0", "\n".join(lines))
        self.summary_text.configure(state="disabled")

    def suggest_next_from_summary(self):
        best = suggest_task_obj()
        if not best:
            messagebox.showinfo("Suggest", "No pending tasks. 🎉")
            return
        messagebox.showinfo(
            "Suggest",
            f"Next Task:\n{best['name']}\nCategory: {best['category']}\n"
            f"Priority: {best['priority']}\nDue: {format_due(best['due'])}"
        )

# ---------------- Run ----------------
if __name__ == "__main__":
    app = ProductivityApp()
    app.mainloop()
