import os
import sys
import json
import tempfile
import subprocess
import time
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# 基础路径定义
CURRENT_DIR = Path(__file__).resolve().parent
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
DRAFT_ROOT = LOCALAPPDATA / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
APP_DIR = LOCALAPPDATA / "JianYingSubtitleExporter"
CONFIG_FILE = APP_DIR / "config.json"

# 优先读取本工具目录自带的 bin/jy-draftc.exe，备选读取 AppData 路径
JY_DRAFTC_EXE = CURRENT_DIR / "bin" / "jy-draftc.exe"
if not JY_DRAFTC_EXE.exists():
    JY_DRAFTC_EXE = APP_DIR / "bin" / "jy-draftc.exe"

# 应用图标（优先取工具目录，其次取 AppData 缓存）
ICON_ICO = CURRENT_DIR / "icon.ico"
if not ICON_ICO.exists():
    ICON_ICO = APP_DIR / "icon.ico"
ICON_PNG = CURRENT_DIR / "icon.png"
if not ICON_PNG.exists():
    ICON_PNG = APP_DIR / "icon.png"

def _dir_of_running_process(name_prefix):
    """在不启动任何子进程（不会闪出控制台窗口）的前提下，
    从正在运行的进程里取出 exe 所在目录。纯 Win32 API 实现。"""
    import ctypes
    from ctypes import wintypes

    TH32CS_SNAPPROCESS = 0x00000002
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.QueryFullProcessImageNameW.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    ]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]

    invalid = ctypes.c_void_p(-1).value
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == invalid:
        return None

    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        prefix = name_prefix.lower()
        while ok:
            if entry.szExeFile.lower().startswith(prefix):
                h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, entry.th32ProcessID)
                if h:
                    try:
                        buf = ctypes.create_unicode_buffer(32768)
                        size = wintypes.DWORD(len(buf))
                        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                            exe = Path(buf.value)
                            if exe.exists():
                                return exe.parent
                    finally:
                        k32.CloseHandle(h)
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return None


def find_jianying_dir():
    """自动寻找包含 videoeditor.dll 的剪映安装目录（全程不启动子进程）"""
    # 1. 剪映正在运行时，直接读它自己的进程路径
    try:
        exe_dir = _dir_of_running_process("Jianying")
        if exe_dir and (exe_dir / "videoeditor.dll").exists():
            return str(exe_dir)
    except Exception:
        pass

    # 2. 官方默认安装路径: %LOCALAPPDATA%\JianyingPro\Apps\<version>\
    apps_dir = LOCALAPPDATA / "JianyingPro" / "Apps"
    if apps_dir.exists():
        versions = [p for p in apps_dir.iterdir() if p.is_dir() and (p / "videoeditor.dll").exists()]
        if versions:
            latest = max(versions, key=lambda p: p.stat().st_mtime)
            return str(latest)

    # 3. 常见自定义安装路径探测
    candidates = [
        Path(r"D:\software\jianying\剪ying\6.0.1.11779"),
        Path(r"D:\software\jianying\剪ying"),
        Path(r"C:\Program Files\JianyingPro"),
        Path(r"D:\Program Files\JianyingPro"),
    ]
    for c in candidates:
        if (c / "videoeditor.dll").exists():
            return str(c)
        if c.exists():
            for sub in c.glob("**/videoeditor.dll"):
                return str(sub.parent)

    return str(apps_dir)

_jy_dir_cache = None


def get_jy_install_dir(refresh=False):
    """懒加载 + 缓存剪映安装目录，避免启动时做无谓探测"""
    global _jy_dir_cache
    if not refresh and _jy_dir_cache:
        cached = Path(_jy_dir_cache)
        if cached.is_dir() and (cached / "videoeditor.dll").exists():
            return _jy_dir_cache
    _jy_dir_cache = find_jianying_dir()
    return _jy_dir_cache

def fmt_time(us):
    ms = int(us / 1000)
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def extract_subtitles_from_json(json_path: Path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    text_map = {}
    for m in data.get("materials", {}).get("texts", []):
        raw = m.get("content", "")
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and "text" in parsed:
                text_map[m["id"]] = parsed["text"]
            else:
                text_map[m["id"]] = raw
        except Exception:
            text_map[m["id"]] = raw

    subs = []
    for tr in data.get("tracks", []):
        if tr.get("type") == "text":
            for seg in tr.get("segments", []):
                mid = seg.get("material_id")
                text = text_map.get(mid, "")
                trange = seg.get("target_timerange", {})
                st = trange.get("start", 0)
                dur = trange.get("duration", 0)
                if text.strip():
                    subs.append((st, st + dur, text))

    subs.sort(key=lambda x: x[0])
    return subs

def get_project_subtitles(draft_dir: Path):
    """提取草稿字幕，支持 6.0+ 加密草稿及明文草稿"""
    content_file = draft_dir / "draft_content.json"
    if not content_file.exists():
        raise FileNotFoundError("草稿中未找到 draft_content.json")

    # 判断是否为明文
    with open(content_file, "rb") as f:
        head = f.read(16).strip()
    
    if head.startswith(b"{"):
        # 明文直接解析
        return extract_subtitles_from_json(content_file)
    
    # 密文草稿：调用 jy-draftc 解密到系统临时目录
    if not JY_DRAFTC_EXE.exists():
        raise FileNotFoundError(f"缺少解密组件: {JY_DRAFTC_EXE}")

    # CREATE_NO_WINDOW：确保解密封装进程不弹出任何控制台窗口
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    def _run_decrypt(jy_dir):
        with tempfile.TemporaryDirectory() as temp_dir:
            cmd = [
                str(JY_DRAFTC_EXE),
                "-dc",
                str(draft_dir),
                "-o",
                temp_dir,
                "--jy-dir",
                jy_dir,
            ]
            res = subprocess.run(
                cmd, capture_output=True, text=True,
                creationflags=no_window,
            )
            if res.returncode != 0:
                raise RuntimeError(f"草稿解密失败: {res.stderr or res.stdout}")

            for root, _, files in os.walk(temp_dir):
                if "draft_content.json" in files:
                    return extract_subtitles_from_json(Path(root) / "draft_content.json")
            raise FileNotFoundError("未能提取解密后的草稿内容")

    try:
        return _run_decrypt(get_jy_install_dir())
    except Exception:
        # 缓存的安装目录可能已失效（剪映升级 / 重装），重新探测一次
        return _run_decrypt(get_jy_install_dir(refresh=True))


class SubtitleExporterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("剪映SRT字幕导出")
        w, h = 880, 580
        self.minsize(750, 480)
        self.configure(bg="#18181c")

        # 启动时在屏幕中央居中显示
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # 状态变量
        self.projects = []
        self.current_subtitles = []
        self.selected_project = None
        self.export_dir = self._load_export_dir()

        self._apply_icon()
        self._setup_style()
        self._build_ui()
        self.load_projects()

    def _apply_icon(self):
        """设置窗口标题栏、任务栏与所有子窗口图标"""
        try:
            if ICON_ICO.exists():
                self.iconbitmap(default=str(ICON_ICO))
        except Exception:
            pass
        try:
            if ICON_PNG.exists():
                self._icon_photo = tk.PhotoImage(file=str(ICON_PNG))
                self.iconphoto(True, self._icon_photo)
        except Exception:
            pass

    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        bg_panel = "#222228"
        fg_text = "#ececf1"

        style.configure("Treeview",
                        background=bg_panel,
                        foreground=fg_text,
                        fieldbackground=bg_panel,
                        rowheight=28,
                        font=("Microsoft YaHei UI", 10))
        style.map("Treeview",
                  background=[("selected", "#383842")],
                  foreground=[("selected", "#00d26a")])

        style.configure("Treeview.Heading",
                        background="#2a2a32",
                        foreground="#9494a8",
                        font=("Microsoft YaHei UI", 10, "bold"),
                        relief="flat")
        style.map("Treeview.Heading",
                  background=[("active", "#33333e")])

    def _build_ui(self):
        # 1. 顶部栏 (始终在最顶层)
        top_frame = tk.Frame(self, bg="#202026", height=52)
        top_frame.pack(fill=tk.X, side=tk.TOP)
        top_frame.pack_propagate(False)

        title_lbl = tk.Label(top_frame, text="🎬 剪映SRT字幕导出", font=("Microsoft YaHei UI", 12, "bold"), fg="#ffffff", bg="#202026")
        title_lbl.pack(side=tk.LEFT, padx=16, pady=10)

        self.status_lbl = tk.Label(top_frame, text="", font=("Microsoft YaHei UI", 9), fg="#ff5c5c", bg="#202026")
        self.status_lbl.pack(side=tk.LEFT, padx=6)

        # 顶部操作按钮 (右上角从左到右：作者 GitHub -> 刷新草稿 -> 导出路径)
        settings_btn = tk.Button(top_frame, text="📁 导出路径", font=("Microsoft YaHei UI", 9),
                                 bg="#2c2c36", fg="#ececf1", activebackground="#383844", activeforeground="#ffffff",
                                 relief="flat", bd=0, padx=12, pady=5, cursor="hand2", command=self.open_settings)
        settings_btn.pack(side=tk.RIGHT, padx=(6, 16), pady=8)

        refresh_btn = tk.Button(top_frame, text="🔄 刷新草稿", font=("Microsoft YaHei UI", 9),
                                bg="#2c2c36", fg="#ececf1", activebackground="#383844", activeforeground="#ffffff",
                                relief="flat", bd=0, padx=12, pady=5, cursor="hand2", command=self.load_projects)
        refresh_btn.pack(side=tk.RIGHT, padx=6, pady=8)

        top_author_btn = tk.Button(top_frame, text="作者 GitHub", font=("Microsoft YaHei UI", 9),
                                   bg="#2c2c36", fg="#ececf1", activebackground="#383844", activeforeground="#00d26a",
                                   relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
                                   command=lambda: webbrowser.open("https://github.com/DQTX760"))
        top_author_btn.pack(side=tk.RIGHT, padx=6, pady=8)

        # 2. 底部操作栏 (必须在 main_paned 之前 pack，避免被挤占空间)
        bot_frame = tk.Frame(self, bg="#202026", height=52)
        bot_frame.pack(fill=tk.X, side=tk.BOTTOM)
        bot_frame.pack_propagate(False)

        self.bot_info = tk.Label(bot_frame, text="", font=("Microsoft YaHei UI", 9), fg="#9494a8", bg="#202026")
        self.bot_info.pack(side=tk.LEFT, padx=16, pady=12)
        self._update_bot_info()

        # (a) 保留现有的“导出字幕”功能 (放置在最右侧核心位置)
        self.bot_export_btn = tk.Button(bot_frame, text="⚡ 导出字幕", font=("Microsoft YaHei UI", 9, "bold"),
                                        bg="#00d26a", fg="#111111", activebackground="#20eb85", activeforeground="#000000",
                                        relief="flat", bd=0, padx=14, pady=6, cursor="hand2", command=self.export_srt)
        self.bot_export_btn.pack(side=tk.RIGHT, padx=(6, 16), pady=8)

        # (b) 将“复制文本”也放到右下角
        self.bot_copy_btn = tk.Button(bot_frame, text="📋 复制文本", font=("Microsoft YaHei UI", 9),
                                      bg="#2c2c36", fg="#ececf1", activebackground="#383844", activeforeground="#ffffff",
                                      relief="flat", bd=0, padx=12, pady=6, cursor="hand2", command=self.copy_text)
        self.bot_copy_btn.pack(side=tk.RIGHT, padx=6, pady=8)

        # 3. 中间主体 (左右分栏，最后填充剩余空间)
        main_paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg="#18181c", sashwidth=4, bd=0)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        # 左侧：草稿列表
        left_frame = tk.Frame(main_paned, bg="#18181c")
        main_paned.add(left_frame, minsize=300, width=330)

        list_head = tk.Label(left_frame, text="本地剪映草稿", font=("Microsoft YaHei UI", 10, "bold"), fg="#ececf1", bg="#18181c")
        list_head.pack(anchor="w", pady=(0, 6))

        tree_frame = tk.Frame(left_frame, bg="#222228")
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=("time",), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="项目名称", anchor="w")
        self.tree.heading("time", text="修改时间", anchor="center")
        self.tree.column("#0", stretch=True, minwidth=140, width=170)
        self.tree.column("time", width=125, minwidth=120, stretch=False, anchor="center")

        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self.on_project_select)
        self.tree.bind("<Double-1>", lambda e: self.export_srt())

        # 右侧：字幕预览
        right_frame = tk.Frame(main_paned, bg="#18181c")
        main_paned.add(right_frame, minsize=380)

        pv_head_frame = tk.Frame(right_frame, bg="#18181c")
        pv_head_frame.pack(fill=tk.X, pady=(0, 6))

        self.pv_title = tk.Label(pv_head_frame, text="字幕预览", font=("Microsoft YaHei UI", 10, "bold"), fg="#ececf1", bg="#18181c")
        self.pv_title.pack(side=tk.LEFT)

        self.pv_count = tk.Label(pv_head_frame, text="", font=("Microsoft YaHei UI", 9), fg="#00d26a", bg="#18181c")
        self.pv_count.pack(side=tk.RIGHT)

        text_frame = tk.Frame(right_frame, bg="#222228", bd=1, relief="flat")
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.preview_text = tk.Text(text_frame, bg="#222228", fg="#ececf1", insertbackground="#ffffff",
                                    font=("Consolas", 10), wrap="word", relief="flat", padx=12, pady=10)
        preview_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scroll.set)
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def load_projects(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not DRAFT_ROOT.exists():
            self.status_lbl.config(text="⚠️ 未找到剪映草稿目录", fg="#ff5c5c")
            return

        projects = []
        for p in DRAFT_ROOT.iterdir():
            if p.is_dir() and (p / "draft_content.json").exists():
                projects.append({
                    "name": p.name,
                    "path": p,
                    "mtime": p.stat().st_mtime
                })

        projects.sort(key=lambda x: x["mtime"], reverse=True)
        self.projects = projects

        for idx, prj in enumerate(projects):
            timestr = time.strftime("%m-%d %H:%M", time.localtime(prj["mtime"]))
            self.tree.insert("", tk.END, iid=str(idx), text=prj["name"], values=(timestr,))

        self.status_lbl.config(text="")

        if projects:
            self.tree.selection_set("0")
            self.on_project_select(None)

    def on_project_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return

        idx = int(selected[0])
        prj = self.projects[idx]
        self.selected_project = prj
        self.pv_title.config(text=f"预览: {prj['name']}")
        self.pv_count.config(text="解析中...", fg="#ffcc00")
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert(tk.END, "正在提取字幕，请稍候...\n")
        self.update_idletasks()

        try:
            subs = get_project_subtitles(prj["path"])
            self.current_subtitles = subs
            self.preview_text.delete("1.0", tk.END)

            if not subs:
                self.pv_count.config(text="无字幕", fg="#9494a8")
                self.preview_text.insert(tk.END, "⚠️ 该草稿中未检测到语音识别字幕。\n请确认已在剪映中执行【文本】→【智能字幕】。")
                return

            self.pv_count.config(text=f"共 {len(subs)} 条字幕", fg="#00d26a")
            for i, (st, et, txt) in enumerate(subs, 1):
                self.preview_text.insert(tk.END, f"[{i:02d}] {fmt_time(st)} → {fmt_time(et)}\n", "timestamp")
                self.preview_text.insert(tk.END, f"     {txt}\n\n")

            self.preview_text.tag_config("timestamp", foreground="#00d26a")
        except Exception as e:
            self.pv_count.config(text="解析失败", fg="#ff5c5c")
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert(tk.END, f"❌ 提取失败: {str(e)}")

    def _load_export_dir(self):
        default_dir = Path.home() / "Desktop"
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    d = cfg.get("export_dir")
                    if d and Path(d).exists():
                        return Path(d)
            except Exception:
                pass
        return default_dir

    def _save_export_dir(self, new_dir: Path):
        self.export_dir = new_dir
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"export_dir": str(new_dir)}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Save config failed:", e)

    def _update_bot_info(self):
        desktop = (Path.home() / "Desktop").resolve()
        if self.export_dir.resolve() == desktop:
            loc_str = "桌面"
        else:
            loc_str = str(self.export_dir)
            if len(loc_str) > 28:
                loc_str = "..." + loc_str[-25:]
        self.bot_info.config(text=f"💡 导出位置: {loc_str} (双击草稿直接导出)")

    def open_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title("导出路径设置")
        dlg.geometry("520x220")
        dlg.resizable(False, False)
        dlg.configure(bg="#18181c")
        dlg.transient(self)
        dlg.grab_set()
        # 子窗口同步应用图标
        try:
            if ICON_ICO.exists():
                dlg.iconbitmap(str(ICON_ICO))
        except Exception:
            pass

        # 居中在主窗口中间显示
        self.update_idletasks()
        pw = self.winfo_width()
        ph = self.winfo_height()
        px = self.winfo_rootx()
        py = self.winfo_rooty()
        dw, dh = 520, 220
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        dlg.geometry(f"{dw}x{dh}+{max(0, x)}+{max(0, y)}")

        lbl = tk.Label(dlg, text="📁 设置字幕导出位置", font=("Microsoft YaHei UI", 11, "bold"), fg="#ffffff", bg="#18181c")
        lbl.pack(anchor="w", padx=20, pady=(18, 10))

        path_frame = tk.Frame(dlg, bg="#18181c")
        path_frame.pack(fill=tk.X, padx=20, pady=5)

        path_var = tk.StringVar(value=str(self.export_dir))
        entry = tk.Entry(path_frame, textvariable=path_var, font=("Consolas", 10), bg="#222228", fg="#ececf1",
                         insertbackground="#ffffff", relief="flat", bd=1)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 8))

        def browse_dir():
            chosen = filedialog.askdirectory(parent=dlg, initialdir=path_var.get(), title="选择字幕导出文件夹")
            if chosen:
                path_var.set(chosen)

        browse_btn = tk.Button(path_frame, text="浏览...", font=("Microsoft YaHei UI", 9),
                               bg="#2c2c36", fg="#ececf1", activebackground="#383844", activeforeground="#ffffff",
                               relief="flat", bd=0, padx=12, pady=5, cursor="hand2", command=browse_dir)
        browse_btn.pack(side=tk.RIGHT)

        def reset_desktop():
            path_var.set(str(Path.home() / "Desktop"))

        reset_btn = tk.Button(dlg, text="🔄 恢复默认 (桌面)", font=("Microsoft YaHei UI", 8),
                              bg="#18181c", fg="#00d26a", activebackground="#18181c", activeforeground="#20eb85",
                              relief="flat", bd=0, cursor="hand2", command=reset_desktop)
        reset_btn.pack(anchor="w", padx=20, pady=(4, 0))

        btn_frame = tk.Frame(dlg, bg="#202026", height=48)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        btn_frame.pack_propagate(False)

        def on_save():
            target = Path(path_var.get().strip())
            if not target.exists():
                try:
                    target.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    messagebox.showerror("路径无效", f"无法创建所选目录: {e}", parent=dlg)
                    return
            self._save_export_dir(target)
            self._update_bot_info()
            dlg.destroy()

        save_btn = tk.Button(btn_frame, text="保存设置", font=("Microsoft YaHei UI", 9, "bold"),
                             bg="#00d26a", fg="#111111", activebackground="#20eb85", activeforeground="#000000",
                             relief="flat", bd=0, padx=16, pady=4, cursor="hand2", command=on_save)
        save_btn.pack(side=tk.RIGHT, padx=16, pady=8)

        cancel_btn = tk.Button(btn_frame, text="取消", font=("Microsoft YaHei UI", 9),
                               bg="#2c2c36", fg="#ececf1", activebackground="#383844", activeforeground="#ffffff",
                               relief="flat", bd=0, padx=12, pady=4, cursor="hand2", command=dlg.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=6, pady=8)

    def show_toast(self, message, is_error=False):
        """无阻塞轻量悬浮提示，自动淡出，无需用户点击确认"""
        color = "#ff5c5c" if is_error else "#00d26a"
        toast = tk.Label(self, text=message, font=("Microsoft YaHei UI", 10, "bold"),
                         bg="#262632", fg=color, padx=18, pady=8,
                         highlightthickness=1, highlightbackground=color, relief="flat")
        toast.place(relx=0.5, rely=0.10, anchor="center")
        self.after(1600, toast.destroy)

    def export_srt(self):
        if not self.selected_project or not self.current_subtitles:
            self.show_toast("⚠️ 当前项目没有可导出的字幕", is_error=True)
            return

        target_dir = self.export_dir
        if not target_dir.exists():
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                target_dir = Path.home() / "Desktop"

        clean_name = "".join(c for c in self.selected_project["name"] if c not in r'\/:*?"<>|').strip()
        srt_file = target_dir / f"{clean_name}_字幕.srt"

        try:
            with open(srt_file, "w", encoding="utf-8") as f:
                for i, (st, et, txt) in enumerate(self.current_subtitles, 1):
                    f.write(f"{i}\n{fmt_time(st)} --> {fmt_time(et)}\n{txt}\n\n")

            # 按钮即时文字反馈 + 悬浮提示，不打断操作
            self.bot_export_btn.config(text="✓ 导出成功！", bg="#20eb85")
            self.after(1600, lambda: self.bot_export_btn.config(text="⚡ 导出字幕", bg="#00d26a"))
            self.show_toast(f"🎉 已成功导出: {srt_file.name}")
        except Exception as e:
            self.show_toast(f"❌ 导出失败: {str(e)}", is_error=True)

    def copy_text(self):
        if not self.current_subtitles:
            self.show_toast("⚠️ 当前没有可复制的字幕文本", is_error=True)
            return

        plain_text = "\n".join(txt for _, _, txt in self.current_subtitles)
        self.clipboard_clear()
        self.clipboard_append(plain_text)

        # 按钮即时文字反馈 + 悬浮提示，不打断操作
        self.bot_copy_btn.config(text="✓ 复制成功！", fg="#00d26a")
        self.after(1600, lambda: self.bot_copy_btn.config(text="📋 复制文本", fg="#ececf1"))
        self.show_toast(f"📋 已复制 {len(self.current_subtitles)} 行字幕文本")


if __name__ == "__main__":
    app = SubtitleExporterApp()
    app.mainloop()
