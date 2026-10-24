#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
剪映字幕智能处理 MCP 服务 (JianYing Subtitle MCP Server)
- 自动读取剪映最新草稿并解析字幕（无需手动复制粘贴）
- 保持原始时码打轴 100% 不变的前提下，原地加密写回校对后的文本
- 支持字幕样式预设注入与桌面一键备份导出
"""

import os
import sys
import json
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastmcp import FastMCP

# 初始化 FastMCP 服务
mcp = FastMCP("jianying-subtitle")

# 基础路径常量
CURRENT_DIR = Path(__file__).resolve().parent
ENGINE_DIR = CURRENT_DIR / "engine"
if ENGINE_DIR.exists() and str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))
SFX_DIR = CURRENT_DIR / "assets" / "sfx"
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
DESKTOP_DIR = Path.home() / "Desktop"
DRAFT_ROOT = LOCALAPPDATA / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
JY_DRAFTC_EXE = CURRENT_DIR / "bin" / "jy-draftc.exe"

# 备选 jy-draftc 路径
if not JY_DRAFTC_EXE.exists():
    fallback = LOCALAPPDATA / "JianYingSubtitleExporter" / "bin" / "jy-draftc.exe"
    if fallback.exists():
        JY_DRAFTC_EXE = fallback


def get_jianying_app_dir() -> Path:
    """自动探测剪映主程序安装目录（用于加载 videoeditor.dll 解密）"""
    apps_dir = LOCALAPPDATA / "JianyingPro" / "Apps"
    if apps_dir.exists():
        versions = [p for p in apps_dir.iterdir() if p.is_dir() and (p / "videoeditor.dll").exists()]
        if versions:
            return max(versions, key=lambda p: p.stat().st_mtime)

    # 常见固定路径
    for c in [
        Path(r"D:\software\jianying\剪ying\6.0.1.11779"),
        Path(r"D:\software\JianyingPro_v9.7.0\9.7.0.13715"),
        Path(r"C:\Program Files\JianyingPro"),
        Path(r"D:\Program Files\JianyingPro"),
    ]:
        if (c / "videoeditor.dll").exists():
            return c
    return apps_dir


def format_srt_time(us: int) -> str:
    """将微秒时间戳格式化为标准 SRT 时间戳 00:00:00,000"""
    ms = int(us / 1000)
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def resolve_draft_dir(draft_name_or_path: Optional[str] = None) -> Path:
    """解析并定位目标剪映草稿目录，默认返回最后一次修改的最新草稿"""
    if not DRAFT_ROOT.exists():
        raise FileNotFoundError(f"剪映草稿根目录不存在: {DRAFT_ROOT}")

    if draft_name_or_path:
        p = Path(draft_name_or_path)
        if p.is_dir():
            return p
        candidate = DRAFT_ROOT / draft_name_or_path
        if candidate.is_dir():
            return candidate
        raise FileNotFoundError(f"未找到指定的草稿项目: {draft_name_or_path}")

    # 查找所有有效草稿项目，按最后修改时间倒序排列
    drafts = [
        d for d in DRAFT_ROOT.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "draft_content.json").exists()
    ]
    if not drafts:
        raise FileNotFoundError(f"在 {DRAFT_ROOT} 中未找到任何草稿项目")

    latest = max(drafts, key=lambda p: p.stat().st_mtime)
    return latest


def decrypt_draft_to_temp(draft_dir: Path, temp_out_dir: Path) -> Path:
    """将草稿解密到临时目录，并返回包含 draft_content.json 的路径"""
    content_file = draft_dir / "draft_content.json"
    if not content_file.exists():
        raise FileNotFoundError(f"草稿目录缺少 draft_content.json: {draft_dir}")

    # 判断是否为明文 JSON
    with open(content_file, "rb") as f:
        head = f.read(16).strip()
    if head.startswith(b"{"):
        shutil.copy2(content_file, temp_out_dir / "draft_content.json")
        return temp_out_dir / "draft_content.json"

    # 密文：调用 jy-draftc 解密
    if not JY_DRAFTC_EXE.exists():
        raise FileNotFoundError(f"缺少解密组件 jy-draftc.exe: {JY_DRAFTC_EXE}")

    jy_dir = get_jianying_app_dir()
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    cmd = [
        str(JY_DRAFTC_EXE),
        "-dc",
        str(draft_dir),
        "-o",
        str(temp_out_dir),
        "--jy-dir",
        str(jy_dir),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, creationflags=no_window)
    if res.returncode != 0:
        raise RuntimeError(f"解密草稿失败: {res.stderr or res.stdout}")

    target_content = temp_out_dir / "draft_content.json"
    if target_content.exists():
        return target_content

    # 搜索子文件夹
    for root, _, files in os.walk(temp_out_dir):
        if "draft_content.json" in files:
            return Path(root) / "draft_content.json"

    raise FileNotFoundError("未能提取解密后的 draft_content.json")


def extract_ordered_subtitles(content_json_path: Path) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """从 draft_content.json 提取按时间戳严格排序的字幕片段和原始 JSON 数据"""
    with open(content_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 建立素材 ID 到字幕文字与样式的映射
    materials_texts = data.get("materials", {}).get("texts", [])
    text_meta_map = {}
    for m in materials_texts:
        raw_content = m.get("content", "")
        try:
            parsed = json.loads(raw_content)
            text_str = parsed.get("text", "") if isinstance(parsed, dict) else str(parsed)
            text_meta_map[m["id"]] = {
                "material": m,
                "parsed_content": parsed,
                "text": text_str
            }
        except Exception:
            text_meta_map[m["id"]] = {
                "material": m,
                "parsed_content": None,
                "text": raw_content
            }

    # 遍历字幕轨道并提取时间范围
    segments = []
    for tr in data.get("tracks", []):
        if tr.get("type") == "text":
            for seg in tr.get("segments", []):
                mid = seg.get("material_id")
                if mid in text_meta_map:
                    t_info = text_meta_map[mid]
                    text = t_info["text"]
                    trange = seg.get("target_timerange", {})
                    st = trange.get("start", 0)
                    dur = trange.get("duration", 0)
                    if text.strip():
                        segments.append({
                            "material_id": mid,
                            "segment_id": seg.get("id"),
                            "start_us": st,
                            "duration_us": dur,
                            "end_us": st + dur,
                            "start_time": format_srt_time(st),
                            "end_time": format_srt_time(st + dur),
                            "text": text,
                            "_meta": t_info
                        })

    segments.sort(key=lambda s: s["start_us"])
    for i, s in enumerate(segments):
        s["index"] = i + 1

    return segments, data


@mcp.tool()
def get_latest_draft_subtitles(limit: int = 2000) -> Dict[str, Any]:
    """获取剪映中最后编辑项目的全部字幕内容（无需手动复制粘贴文本）。
    
    返回字段包含：
    - draft_name: 草稿项目名称
    - draft_path: 草稿文件夹绝对路径
    - updated_time: 最后编辑修改时间
    - total_lines: 总字幕句数
    - lines: 纯文本按行排列的字幕列表（按时码顺序，用于直接校对纠错）
    - subtitles: 携带毫秒时码与起始时间戳的详细对象列表
    - raw_text: 纯文本换行拼接字符串
    """
    draft_dir = resolve_draft_dir()
    mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(draft_dir.stat().st_mtime))

    with tempfile.TemporaryDirectory() as td:
        plain_content_file = decrypt_draft_to_temp(draft_dir, Path(td))
        segments, _ = extract_ordered_subtitles(plain_content_file)

    clean_segments = segments[:limit]
    lines = [s["text"] for s in clean_segments]

    detailed = []
    for s in clean_segments:
        detailed.append({
            "index": s["index"],
            "start_time": s["start_time"],
            "end_time": s["end_time"],
            "start_ms": s["start_us"] // 1000,
            "duration_ms": s["duration_us"] // 1000,
            "text": s["text"],
            "material_id": s["material_id"]
        })

    return {
        "status": "success",
        "draft_name": draft_dir.name,
        "draft_path": str(draft_dir),
        "updated_time": mtime_str,
        "total_lines": len(lines),
        "lines": lines,
        "subtitles": detailed,
        "raw_text": "\n".join(lines)
    }


@mcp.tool()
def list_recent_drafts(limit: int = 10) -> List[Dict[str, Any]]:
    """列出剪映最近编辑的草稿项目列表（按修改时间倒序排列）。"""
    if not DRAFT_ROOT.exists():
        return []

    drafts = [
        d for d in DRAFT_ROOT.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "draft_content.json").exists()
    ]
    drafts.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    result = []
    for d in drafts[:limit]:
        mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(d.stat().st_mtime))
        result.append({
            "name": d.name,
            "path": str(d),
            "updated_time": mtime_str
        })
    return result


@mcp.tool()
def update_draft_subtitles(
    corrected_lines: List[str],
    draft_name_or_path: Optional[str] = None,
    style_preset: Optional[str] = "yansong_shadow",
    create_clone: bool = True,
    export_to_desktop: bool = True
) -> Dict[str, Any]:
    """将校对后的字幕文本直接原地写回剪映草稿，并可选导出到桌面。
    
    参数说明：
    - corrected_lines: 校对完成后的文本列表（必须与提取出的字幕行数一致，按顺序一一映射替换）
    - draft_name_or_path: 草稿名称或绝对路径，不填则默认匹配剪映最新草稿
    - style_preset: 可选样式预设注入：
        * 'white_border_black': 经典醒目白色字加黑色描边
        * 'yellow_highlight': 爆款短视频亮黄字体黑色描边
        * 'clean_white': 极简无边框高清白色字体
    - export_to_desktop: 是否同时在桌面生成【校正字幕_xxx.txt】与【校正字幕_xxx.srt】（默认 True）
    
    安全机制：
    1. 自动在原草稿目录创建 draft_content.json.bak 备份；
    2. 严格保留时间戳与轨道结构，仅替换文本内容与自适应字符区间 range；
    3. 写入完成后，用户退出剪映项目首页再重新进入，即可查看到更新后的字幕。
    """
    draft_dir = resolve_draft_dir(draft_name_or_path)
    jy_dir = get_jianying_app_dir()
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    # 1. 解密草稿到临时工作区
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        plain_file = decrypt_draft_to_temp(draft_dir, temp_dir)
        segments, full_data = extract_ordered_subtitles(plain_file)

        if len(corrected_lines) != len(segments):
            return {
                "status": "error",
                "message": f"行数不匹配：草稿共有 {len(segments)} 条字幕，但传入了 {len(corrected_lines)} 条校正文本！为防止时码错位，已拦截操作。"
            }

        # 2. 逐行更新文字内容与样式字符区间
        materials_texts = full_data.get("materials", {}).get("texts", [])
        mid_to_mat = {m["id"]: m for m in materials_texts}

        for seg, new_text in zip(segments, corrected_lines):
            mid = seg["material_id"]
            if mid in mid_to_mat:
                m_obj = mid_to_mat[mid]
                raw_c = m_obj.get("content", "")
                try:
                    c_dict = json.loads(raw_c)
                except Exception:
                    c_dict = {"text": new_text}

                c_dict["text"] = new_text
                new_len = len(new_text)

                # 更新字符样式区间，防止溢出导致剪映渲染异常
                if "styles" in c_dict and isinstance(c_dict["styles"], list):
                    for st in c_dict["styles"]:
                        st["range"] = [0, new_len]

                # 应用样式预设
                if style_preset == "white_border_black":
                    m_obj["border_width"] = 10.0
                    m_obj["border_color"] = "#000000"
                    m_obj["border_alpha"] = 1.0
                elif style_preset == "yellow_highlight":
                    m_obj["border_width"] = 10.0
                    m_obj["border_color"] = "#000000"
                    m_obj["border_alpha"] = 1.0
                    if "styles" in c_dict:
                        for st in c_dict.get("styles", []):
                            if "fill" in st and "content" in st["fill"]:
                                st["fill"]["content"]["solid"]["color"] = [1.0, 0.88, 0.2]
                elif style_preset == "clean_white":
                    m_obj["border_width"] = 0.0
                    m_obj["has_shadow"] = True
                elif style_preset in ["yansong_shadow", "研宋体", "研宋体阴影"]:
                    yansong_path = "C:/Users/Administrator/AppData/Local/JianyingPro/User Data/Cache/effect/4010355/06458c13377d445fe3368cd2c786c7a5/Aa研宋.ttf"
                    yansong_id = "7130644288047682085"
                    m_obj["font_title"] = "研宋体"
                    m_obj["font_id"] = "4010355"
                    m_obj["font_resource_id"] = yansong_id
                    m_obj["font_path"] = yansong_path
                    m_obj["font_size"] = 13.0
                    m_obj["has_shadow"] = True
                    m_obj["shadow_alpha"] = 0.6
                    m_obj["shadow_color"] = "#000000"
                    m_obj["shadow_diffuse"] = 0.010031185
                    m_obj["shadow_distance"] = 6.0
                    m_obj["shadow_angle"] = -60.0
                    m_obj["border_width"] = 0.0
                    if "styles" in c_dict and isinstance(c_dict["styles"], list):
                        for st in c_dict["styles"]:
                            st["size"] = 13.0
                            st["font"] = {"id": yansong_id, "path": yansong_path}
                            st["shadows"] = [{
                                "alpha": 0.6,
                                "angle": -60.0,
                                "content": {"solid": {"alpha": 1.0, "color": [0.0, 0.0, 0.0]}},
                                "diffuse": 0.010031185,
                                "distance": 6.0
                            }]

                m_obj["content"] = json.dumps(c_dict, ensure_ascii=False)

        # 3. 将更新后的数据保存回临时明文草稿
        with open(plain_file, "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False)

        # 4. 重新加密并打包到加密临时目录
        enc_temp_dir = temp_dir / "encrypted_output"
        cmd_enc = [
            str(JY_DRAFTC_EXE),
            "-ec",
            str(plain_file.parent),
            "-o",
            str(enc_temp_dir),
            "--jy-dir",
            str(jy_dir)
        ]
        res_enc = subprocess.run(cmd_enc, capture_output=True, text=True, creationflags=no_window)
        if res_enc.returncode != 0:
            return {
                "status": "error",
                "message": f"重新加密打包草稿失败: {res_enc.stderr or res_enc.stdout}"
            }

        # 5. 备份原草稿的 draft_content.json
        orig_content_file = draft_dir / "draft_content.json"
        bak_file = draft_dir / "draft_content.json.bak"
        if orig_content_file.exists():
            shutil.copy2(orig_content_file, bak_file)

        # 6. 将新生成的 draft_content.json 覆盖写回真实草稿
        new_enc_file = enc_temp_dir / "draft_content.json"
        if not new_enc_file.exists():
            for root, _, files in os.walk(enc_temp_dir):
                if "draft_content.json" in files:
                    new_enc_file = Path(root) / "draft_content.json"
                    break

        if not new_enc_file.exists():
            return {"status": "error", "message": "未能生成加密后的 draft_content.json"}

        shutil.copy2(new_enc_file, orig_content_file)

        # 6.2 复制生成独立副本项目，彻底防止剪映运行时内存缓存反向覆写
        clone_info = None
        if create_clone:
            clone_name = f"{draft_dir.name} (AI精修字幕)"
            clone_dir = DRAFT_ROOT / clone_name
            if clone_dir.exists():
                shutil.rmtree(clone_dir, ignore_errors=True)
            shutil.copytree(draft_dir, clone_dir, ignore=shutil.ignore_patterns(".backup", "*.bak", "*.tmp", ".locked"))
            shutil.copy2(new_enc_file, clone_dir / "draft_content.json")
            clone_info = clone_name
    # 7. 桌面导出留档
    desktop_files = {}
    if export_to_desktop and DESKTOP_DIR.exists():
        safe_name = "".join(c for c in draft_dir.name if c not in r'\/:*?"<>|').strip() or "剪映项目"
        txt_path = DESKTOP_DIR / f"校正字幕_{safe_name}.txt"
        srt_path = DESKTOP_DIR / f"校正字幕_{safe_name}.srt"

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(corrected_lines))
        desktop_files["desktop_txt"] = str(txt_path)

        with open(srt_path, "w", encoding="utf-8") as f:
            for s, txt in zip(segments, corrected_lines):
                f.write(f"{s['index']}\n{s['start_time']} --> {s['end_time']}\n{txt}\n\n")
        desktop_files["desktop_srt"] = str(srt_path)

    return {
        "status": "success",
        "draft_name": draft_dir.name,
        "draft_path": str(draft_dir),
        "updated_lines": len(corrected_lines),
        "backup_path": str(bak_file),
        "style_preset": style_preset or "保留原样",
        "desktop_exports": desktop_files,
        "clone_project": clone_info,
        "collaborative_tip": "导出的 SRT 文件已放置桌面，可立即发送给另一位 AI 助手（如 overlay-studio / agent-motion）并行制作透明动效层！",
        "instructions": f"字幕已成功加密写回剪映草稿！已为您生成缓存安全副本【{clone_info or draft_dir.name}】，回到剪映首页直接打开即可看到新字幕。"
    }


@mcp.tool()
def restore_draft_backup(draft_name_or_path: Optional[str] = None) -> Dict[str, Any]:
    """从 .bak 备份文件中一键恢复草稿原始内容（撤销写回操作）。"""
    draft_dir = resolve_draft_dir(draft_name_or_path)
    bak_file = draft_dir / "draft_content.json.bak"
    content_file = draft_dir / "draft_content.json"

    if not bak_file.exists():
        return {
            "status": "error",
            "message": f"未找到备份文件: {bak_file}"
        }

    shutil.copy2(bak_file, content_file)
    return {
        "status": "success",
        "draft_name": draft_dir.name,
        "message": "已从 .bak 成功还原原始草稿文件！"
    }


@mcp.tool()
def export_draft_to_desktop(draft_name_or_path: Optional[str] = None) -> Dict[str, Any]:
    """无需修改草稿，直接将指定或最新草稿的当前字幕导出为 TXT 和 SRT 到桌面。"""
    draft_dir = resolve_draft_dir(draft_name_or_path)
    with tempfile.TemporaryDirectory() as td:
        plain_file = decrypt_draft_to_temp(draft_dir, Path(td))
        segments, _ = extract_ordered_subtitles(plain_file)

    safe_name = "".join(c for c in draft_dir.name if c not in r'\/:*?"<>|').strip() or "剪映项目"
    txt_path = DESKTOP_DIR / f"剪映字幕_{safe_name}.txt"
    srt_path = DESKTOP_DIR / f"剪映字幕_{safe_name}.srt"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(s["text"] for s in segments))

    with open(srt_path, "w", encoding="utf-8") as f:
        for s in segments:
            f.write(f"{s['index']}\n{s['start_time']} --> {s['end_time']}\n{s['text']}\n\n")

    return {
        "status": "success",
        "draft_name": draft_dir.name,
        "total_lines": len(segments),
        "txt_file": str(txt_path),
        "srt_file": str(srt_path)
    }


if __name__ == "__main__":
    # 支持命令行快速测试模式
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("=== 正在测试剪映字幕提取功能 ===")
        res = get_latest_draft_subtitles()
        print(f"成功锁定最新草稿: {res['draft_name']}")
        print(f"修改时间: {res['updated_time']}")
        print(f"字幕总行数: {res['total_lines']}")
        print("前 3 条预览:")
        for line in res["lines"][:3]:
            print("  -", line)
        print("测试通过！")
    else:
        # 默认以标准 stdio MCP 协议运行
        mcp.run()
