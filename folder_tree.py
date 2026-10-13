"""Folder Tree Viewer - vẽ cấu trúc cây của một thư mục.

Chạy:  python folder_tree.py [đường_dẫn]
Chỉ dùng thư viện chuẩn (tkinter), không cần cài thêm gì.
"""

import fnmatch
import os
import stat
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

DEFAULT_IGNORE = ".git, __pycache__, node_modules, .venv, .idea, .vs"


class Node:
    __slots__ = ("name", "path", "is_dir", "size", "children", "error", "truncated")

    def __init__(self, name, path, is_dir):
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.size = 0
        self.children = []
        self.error = None
        self.truncated = False  # thư mục có nội dung nhưng bị cắt do giới hạn độ sâu


def human_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def is_hidden(entry):
    if entry.name.startswith("."):
        return True
    try:
        attrs = entry.stat(follow_symlinks=False).st_file_attributes
        return bool(attrs & stat.FILE_ATTRIBUTE_HIDDEN)
    except (AttributeError, OSError):
        return False


class Scanner:
    """Quét thư mục trong thread nền, đếm tiến độ để UI hiển thị."""

    def __init__(self, root_path, max_depth, show_hidden, ignore_patterns):
        self.root_path = root_path
        self.max_depth = max_depth  # 0 = không giới hạn
        self.show_hidden = show_hidden
        self.ignore_patterns = ignore_patterns
        self.cancel = threading.Event()
        self.count = 0
        self.folders = 0
        self.files = 0
        self.result = None
        self.exception = None

    def run(self):
        try:
            name = os.path.basename(os.path.normpath(self.root_path)) or self.root_path
            root = Node(name, self.root_path, True)
            self._scan(root, 1)
            self.result = root
        except Exception as e:  # noqa: BLE001 - báo lỗi bất kỳ lên UI
            self.exception = e

    def _ignored(self, name):
        return any(fnmatch.fnmatch(name, p) for p in self.ignore_patterns)

    def _scan(self, node, depth):
        if self.cancel.is_set():
            return
        try:
            with os.scandir(node.path) as it:
                entries = list(it)
        except OSError as e:
            node.error = e.strerror or str(e)
            return

        entries = [
            e for e in entries
            if not self._ignored(e.name) and (self.show_hidden or not is_hidden(e))
        ]
        # Thư mục trước, file sau, sắp xếp không phân biệt hoa thường
        entries.sort(key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))

        if self.max_depth and depth > self.max_depth:
            node.truncated = bool(entries)
            return

        for entry in entries:
            if self.cancel.is_set():
                return
            is_dir = entry.is_dir(follow_symlinks=False)
            child = Node(entry.name, entry.path, is_dir)
            self.count += 1
            if is_dir:
                self.folders += 1
                # Không đi vào junction (Windows) để tránh vòng lặp vô hạn
                if not getattr(entry, "is_junction", lambda: False)():
                    self._scan(child, depth + 1)
            else:
                self.files += 1
                try:
                    child.size = entry.stat(follow_symlinks=False).st_size
                except OSError:
                    pass
            node.size += child.size
            node.children.append(child)


def build_text_tree(root, show_size):
    lines = [f"{root.name}/" + (f"  ({human_size(root.size)})" if show_size else "")]

    def walk(node, prefix):
        last_index = len(node.children) - 1
        for i, child in enumerate(node.children):
            last = i == last_index
            label = child.name + ("/" if child.is_dir else "")
            if show_size:
                label += f"  ({human_size(child.size)})"
            if child.error:
                label += f"  [lỗi: {child.error}]"
            if child.truncated:
                label += "  [...]"
            lines.append(prefix + ("└── " if last else "├── ") + label)
            if child.children:
                walk(child, prefix + ("    " if last else "│   "))

    walk(root, "")
    return "\n".join(lines)


def make_icon(kind):
    """Vẽ icon 16x16 đơn giản bằng PhotoImage (không cần file ảnh)."""
    img = tk.PhotoImage(width=16, height=16)
    if kind == "folder":
        img.put("#d9a400", to=(1, 3, 7, 5))      # tab
        img.put("#f5c518", to=(1, 5, 15, 14))    # thân
        img.put("#d9a400", to=(1, 13, 15, 14))   # viền dưới
    elif kind == "error":
        img.put("#c62828", to=(3, 3, 13, 13))
        img.put("#ffffff", to=(7, 5, 9, 9))
        img.put("#ffffff", to=(7, 10, 9, 12))
    else:
        img.put("#9e9e9e", to=(3, 1, 13, 15))    # viền
        img.put("#ffffff", to=(4, 2, 12, 14))    # giấy
        for y in (5, 8, 11):
            img.put("#64b5f6", to=(5, y, 11, y + 1))
    return img


class App(tk.Tk):
    def __init__(self, initial_path=""):
        super().__init__()
        self.title("Folder Tree Viewer")
        self.geometry("1000x680")
        self.minsize(700, 450)

        self.icons = {k: make_icon(k) for k in ("folder", "file", "error")}
        self.node_by_iid = {}
        self.root_node = None
        self.scanner = None

        self.path_var = tk.StringVar(value=initial_path)
        self.depth_var = tk.IntVar(value=0)
        self.hidden_var = tk.BooleanVar(value=False)
        self.size_var = tk.BooleanVar(value=True)
        self.ignore_var = tk.StringVar(value=DEFAULT_IGNORE)
        self.status_var = tk.StringVar(value="Chọn thư mục rồi bấm 'Vẽ cây'.")

        self._build_ui()
        if initial_path:
            self.after(100, self.start_scan)

    # ---------- UI ----------
    def _build_ui(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=22)

        top = ttk.Frame(self, padding=(10, 10, 10, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Thư mục:").pack(side="left")
        entry = ttk.Entry(top, textvariable=self.path_var)
        entry.pack(side="left", fill="x", expand=True, padx=6)
        entry.bind("<Return>", lambda e: self.start_scan())
        ttk.Button(top, text="Chọn...", command=self.browse).pack(side="left")
        self.run_btn = ttk.Button(top, text="Vẽ cây", command=self.start_scan)
        self.run_btn.pack(side="left", padx=(6, 0))

        opts = ttk.Frame(self, padding=(10, 0, 10, 6))
        opts.pack(fill="x")
        ttk.Label(opts, text="Độ sâu tối đa (0 = tất cả):").pack(side="left")
        ttk.Spinbox(opts, from_=0, to=99, width=4, textvariable=self.depth_var).pack(
            side="left", padx=(4, 12))
        ttk.Checkbutton(opts, text="Hiện file ẩn", variable=self.hidden_var).pack(side="left")
        ttk.Checkbutton(opts, text="Hiện dung lượng", variable=self.size_var,
                        command=self.refresh_text).pack(side="left", padx=(12, 12))
        ttk.Label(opts, text="Bỏ qua:").pack(side="left")
        ttk.Entry(opts, textvariable=self.ignore_var).pack(side="left", fill="x", expand=True,
                                                           padx=(4, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10)

        # Tab 1: cây tương tác
        tree_tab = ttk.Frame(self.notebook)
        self.notebook.add(tree_tab, text="  Cây thư mục  ")
        bar = ttk.Frame(tree_tab, padding=(0, 6))
        bar.pack(fill="x")
        ttk.Button(bar, text="Mở rộng tất cả", command=lambda: self.set_open_all(True)).pack(
            side="left")
        ttk.Button(bar, text="Thu gọn tất cả", command=lambda: self.set_open_all(False)).pack(
            side="left", padx=6)
        ttk.Label(bar, text="Double-click file để mở, chuột phải để mở trong Explorer.",
                  foreground="#777").pack(side="right")

        frame = ttk.Frame(tree_tab)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("size", "items"), selectmode="browse")
        self.tree.heading("#0", text="Tên", anchor="w")
        self.tree.heading("size", text="Dung lượng", anchor="e")
        self.tree.heading("items", text="Số mục", anchor="e")
        self.tree.column("#0", width=600, stretch=True)
        self.tree.column("size", width=110, anchor="e", stretch=False)
        self.tree.column("items", width=80, anchor="e", stretch=False)
        self.tree.tag_configure("error", foreground="#c62828")
        ysb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewOpen>>", self.on_open)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)

        # Tab 2: dạng văn bản (giống lệnh `tree`)
        text_tab = ttk.Frame(self.notebook)
        self.notebook.add(text_tab, text="  Dạng văn bản  ")
        bar2 = ttk.Frame(text_tab, padding=(0, 6))
        bar2.pack(fill="x")
        ttk.Button(bar2, text="Copy", command=self.copy_text).pack(side="left")
        ttk.Button(bar2, text="Lưu ra file .txt", command=self.save_text).pack(side="left", padx=6)
        tframe = ttk.Frame(text_tab)
        tframe.pack(fill="both", expand=True)
        self.text = tk.Text(tframe, wrap="none", font=("Consolas", 10), undo=False)
        tys = ttk.Scrollbar(tframe, orient="vertical", command=self.text.yview)
        txs = ttk.Scrollbar(tframe, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=tys.set, xscrollcommand=txs.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        tys.grid(row=0, column=1, sticky="ns")
        txs.grid(row=1, column=0, sticky="ew")
        tframe.rowconfigure(0, weight=1)
        tframe.columnconfigure(0, weight=1)

        status = ttk.Frame(self, padding=(10, 4))
        status.pack(fill="x")
        self.progress = ttk.Progressbar(status, mode="indeterminate", length=120)
        ttk.Label(status, textvariable=self.status_var).pack(side="left")

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Mở", command=lambda: self.open_selected(False))
        self.menu.add_command(label="Mở trong Explorer", command=lambda: self.open_selected(True))
        self.menu.add_command(label="Copy đường dẫn", command=self.copy_selected_path)

    # ---------- Quét ----------
    def browse(self):
        path = filedialog.askdirectory(initialdir=self.path_var.get() or os.getcwd())
        if path:
            self.path_var.set(os.path.normpath(path))
            self.start_scan()

    def start_scan(self):
        if self.scanner:  # đang quét -> nút đóng vai trò "Dừng"
            self.scanner.cancel.set()
            return
        path = self.path_var.get().strip().strip('"')
        if not path or not os.path.isdir(path):
            messagebox.showerror("Lỗi", f"Đường dẫn không tồn tại hoặc không phải thư mục:\n{path}")
            return
        try:
            depth = max(0, int(self.depth_var.get()))
        except (tk.TclError, ValueError):
            depth = 0
        patterns = [p.strip() for p in self.ignore_var.get().split(",") if p.strip()]

        self.scanner = Scanner(os.path.abspath(path), depth, self.hidden_var.get(), patterns)
        threading.Thread(target=self.scanner.run, daemon=True).start()
        self.run_btn.configure(text="Dừng")
        self.progress.pack(side="right")
        self.progress.start(12)
        self.poll_scan()

    def poll_scan(self):
        s = self.scanner
        if s.result is None and s.exception is None:
            self.status_var.set(f"Đang quét... {s.count:,} mục")
            self.after(100, self.poll_scan)
            return

        self.scanner = None
        self.progress.stop()
        self.progress.pack_forget()
        self.run_btn.configure(text="Vẽ cây")
        if s.exception:
            messagebox.showerror("Lỗi", str(s.exception))
            self.status_var.set("Quét thất bại.")
            return

        self.root_node = s.result
        self.populate_tree()
        self.refresh_text()
        msg = (f"{s.folders:,} thư mục, {s.files:,} file, "
               f"tổng {human_size(self.root_node.size)}  —  {self.root_node.path}")
        if s.cancel.is_set():
            msg = "Đã dừng (kết quả chưa đầy đủ): " + msg
        self.status_var.set(msg)

    # ---------- Treeview (nạp lười khi mở nhánh để nhanh với thư mục lớn) ----------
    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.node_by_iid.clear()
        iid = self._insert("", self.root_node)
        self.tree.item(iid, open=True)
        self._load_children(iid)

    def _insert(self, parent, node):
        if node.error:
            icon, tags = self.icons["error"], ("error",)
            text = f"{node.name}   [lỗi: {node.error}]"
        else:
            icon, tags = self.icons["folder" if node.is_dir else "file"], ()
            text = node.name + ("   [...]" if node.truncated else "")
        items = f"{len(node.children):,}" if node.is_dir else ""
        iid = self.tree.insert(parent, "end", text=" " + text, image=icon,
                               values=(human_size(node.size), items), tags=tags)
        self.node_by_iid[iid] = node
        if node.children:
            self.tree.insert(iid, "end", text="")  # node giả để hiện dấu mở rộng
        return iid

    def _load_children(self, iid):
        node = self.node_by_iid[iid]
        kids = self.tree.get_children(iid)
        if len(kids) == 1 and kids[0] not in self.node_by_iid:
            self.tree.delete(kids[0])
            for child in node.children:
                self._insert(iid, child)

    def on_open(self, _event):
        iid = self.tree.focus()
        if iid in self.node_by_iid:
            self._load_children(iid)

    def set_open_all(self, open_):
        if not self.root_node:
            return
        if open_:
            total = sum(1 for _ in self._iter_nodes(self.root_node))
            if total > 20000 and not messagebox.askyesno(
                    "Xác nhận", f"Có {total:,} mục, mở rộng tất cả có thể chậm. Tiếp tục?"):
                return

        def walk(iid):
            if open_:
                self._load_children(iid)
            self.tree.item(iid, open=open_)
            for child in self.tree.get_children(iid):
                if child in self.node_by_iid and self.node_by_iid[child].is_dir:
                    walk(child)

        for iid in self.tree.get_children(""):
            walk(iid)
            if not open_:
                self.tree.item(iid, open=True)  # giữ gốc luôn mở

    def _iter_nodes(self, node):
        yield node
        for c in node.children:
            yield from self._iter_nodes(c)

    # ---------- Hành động trên item ----------
    def _selected_node(self):
        iid = self.tree.focus()
        return self.node_by_iid.get(iid)

    def on_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        node = self.node_by_iid.get(iid)
        if node and not node.is_dir:
            self.open_selected(False)

    def on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid in self.node_by_iid:
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.menu.tk_popup(event.x_root, event.y_root)

    def open_selected(self, in_explorer):
        node = self._selected_node()
        if not node:
            return
        try:
            if in_explorer and sys.platform == "win32":
                import subprocess
                subprocess.Popen(["explorer", "/select,", os.path.normpath(node.path)])
            elif sys.platform == "win32":
                os.startfile(node.path)
            else:
                import subprocess
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                target = os.path.dirname(node.path) if in_explorer else node.path
                subprocess.Popen([opener, target])
        except OSError as e:
            messagebox.showerror("Lỗi", str(e))

    def copy_selected_path(self):
        node = self._selected_node()
        if node:
            self.clipboard_clear()
            self.clipboard_append(node.path)

    # ---------- Tab văn bản ----------
    def refresh_text(self):
        if not self.root_node:
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", build_text_tree(self.root_node, self.size_var.get()))

    def copy_text(self):
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end-1c"))
        self.status_var.set("Đã copy cây thư mục vào clipboard.")

    def save_text(self):
        if not self.root_node:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", initialfile=f"{self.root_node.name}_tree.txt",
            filetypes=[("Text file", "*.txt"), ("Tất cả", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text.get("1.0", "end-1c"))
            self.status_var.set(f"Đã lưu: {path}")


if __name__ == "__main__":
    App(sys.argv[1] if len(sys.argv) > 1 else "").mainloop()
