#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
剪映口播字幕一键极速优化引擎 (One-Click Subtitle Optimizer CLI & Module)
- 零代码生成耗时，1条命令 2.5 秒内全流程端到端搞定！
- 核心沉淀规范:
  1. 逐字稿 100% 行数守恒，时间轴零切碎；
  2. 标点彻底清空，长句按语义自然插入 \\n 换行，绝无单字掉行（寡字）与倒金字塔失衡；
  3. Aa研宋体 (13.0) + 60% 立体阴影；
  4. 句内核心重点词放大至 16.5 + 加粗 + 亮金黄高饱和高亮；
  5. 竖屏 9:16 终极黄金安全区 y = -0.42 (完美避让抖音章节横条与文案上浮)；
  6. 5~8 处关键情绪节点注入场景匹配免费轻动效 (0.4s) 与卡点留存音效 (vol 0.60)；
  7. 主视频人声音量精准增益至标准 +7.0 dB；
  8. UI 自动化无感释放内存锁 + 原地多副本加密同步 + 原地重载打开！
"""

import os
import re
import sys
import copy
import json
import time
import uuid
import shutil
import tempfile
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

CURRENT_DIR = Path(__file__).resolve().parent
ENGINE_DIR = CURRENT_DIR / "engine"
if ENGINE_DIR.exists() and str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

SFX_DIR = CURRENT_DIR / "assets" / "sfx"
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
DRAFT_ROOT = LOCALAPPDATA / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
JY_DRAFTC = CURRENT_DIR / "bin" / "jy-draftc.exe"
JY_INSTALL = Path(r"C:\Users\Administrator\AppData\Local\JianyingPro\Apps\8.9.0.13361")

YANSONG_ID = "7130644288047682085"
YANSONG_PATH = "C:/Users/Administrator/AppData/Local/JianyingPro/User Data/Cache/effect/4010355/06458c13377d445fe3368cd2c786c7a5/Aa研宋.ttf"

SHADOW_SPEC = [{
    "alpha": 0.6,
    "angle": -60.0,
    "content": {"solid": {"alpha": 1.0, "color": [0.0, 0.0, 0.0]}},
    "diffuse": 0.010031185,
    "distance": 6.0
}]

# 描边：录屏类视频常常白底网页与深色网页交替出现，任何单一字色都会在某半边糊掉。
# 白字 + 黑描边 + 阴影是唯一在明暗背景上都成立的组合。
STROKE_WIDTH = 40.0          # 与剪映一致，取值 0~100
STROKE_ALPHA = 0.9
STROKE_COLOR = [0.0, 0.0, 0.0]
STROKE_SPEC = [{
    "content": {"solid": {"alpha": STROKE_ALPHA, "color": STROKE_COLOR}},
    "width": STROKE_WIDTH / 100.0 * 0.2
}]
CHECK_FLAG = 7 | 8 | 32      # 描边(8) + 阴影(32) 必须同时置位，否则剪映不渲染
SFX_TRACK_NAME = "留存音效轨 (卡点进场搭配)"

# 动画资产库 (全部免费)
ANIM_LIB = {
    "whoosh": {"name": "向右缓入", "id": "1488722", "res": "7043778124760224292", "dur": 400000},
    "type": {"name": "打字机 I", "id": "1644275", "res": "6724920249654710791", "dur": 400000},
    "pop": {"name": "向上滑动", "id": "1644267", "res": "6763470111253729803", "dur": 400000},
    "thud": {"name": "轻微放大", "id": "1644262", "res": "6763469998330483213", "dur": 400000},
    "zoom": {"name": "放大", "id": "1644264", "res": "6724919499042066958", "dur": 350000},
    "sunrise": {"name": "日出", "id": "1644269", "res": "6779084126457696776", "dur": 500000},
    "flip": {"name": "向上翻转", "id": "8945307", "res": "7194703971498332727", "dur": 400000}
}


def get_latest_draft_dir() -> Path:
    """获取最后修改的草稿目录"""
    if not DRAFT_ROOT.exists():
        raise FileNotFoundError(f"剪映草稿目录不存在: {DRAFT_ROOT}")
    dirs = [d for d in DRAFT_ROOT.iterdir() if d.is_dir() and (d / "draft_content.json").exists()]
    if not dirs:
        raise FileNotFoundError("未找到任何剪映草稿项目！")
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return dirs[0]


def clean_and_balance_line(raw_text: str, single_line: bool = True) -> str:
    """
    标点清洗与单行/匀称排版算法:
    - 彻底删除首尾和中间标点符号；
    - single_line=True (默认): 保证单行顺次滚动（绝无 \\n 换行，绝无双行堆叠）；
    - single_line=False: 兼容双行折行排版。
    """
    clean = raw_text.strip().rstrip("，。！？,.!? ")
    if not clean:
        return ""

    if single_line:
        # 纯单行模式：替换所有换行与逗号为空格或直接连接
        clean_single = clean.replace("\n", " ").replace("，", " ").replace(",", " ")
        # 清理多余连续空格与标点
        return " ".join([p.strip().rstrip("，。！？,.!? ") for p in clean_single.split(" ") if p.strip()])
    # 如果本身已有换行，保持清洗后的内容
    if "\n" in clean:
        parts = [p.strip().rstrip("，。！？,.!? ") for p in clean.split("\n") if p.strip()]
        return "\n".join(parts)

    # 包含中文逗号时的智能切分
    if "，" in clean:
        parts = clean.split("，")
        p0, p1 = parts[0].strip(), parts[1].strip()
        # 避免寡词: 如果前段只有 2~3 个字且后段很长 (> 8字)
        if len(p0) <= 3 and len(p1) >= 8:
            # 尝试在后段找连词或主谓停顿
            sub_split = None
            for break_word in ["我会用", "如果我的内容", "我想", "能产生", "我们"]:
                if break_word in p1:
                    idx = p1.find(break_word) + len(break_word)
                    p0 = f"{p0} {p1[:idx]}"
                    p1 = p1[idx:]
                    sub_split = True
                    break
            if sub_split:
                return f"{p0}\n{p1}"

        if len(clean) > 10:
            return f"{p0}\n{p1}"
        else:
            return f"{p0} {p1}"

    # 没有逗号的长句 (> 11字)，自动寻找语义对称折行点
    if len(clean) > 11:
        half = len(clean) // 2
        # 在中间 ±3 字范围内寻找虚词、连词切分
        best_pos = None
        for kw in ["和我一起", "的", "一个", "出来", "每个", "这个项目", "在实践中", "去描述"]:
            if kw in clean:
                pos = clean.find(kw)
                if abs(pos - half) <= 3 and pos > 3 and (len(clean) - pos) >= 3:
                    best_pos = pos + (len(kw) if len(kw) <= 2 else 0)
                    break
        if best_pos and 3 <= best_pos <= len(clean) - 3:
            return f"{clean[:best_pos]}\n{clean[best_pos:]}"
        else:
            # 直接对称切分，确保第二行绝不掉单字 (至少 4 字)
            cut = max(half, len(clean) - 5)
            if cut < len(clean) - 1:
                return f"{clean[:cut]}\n{clean[cut:]}"

    return clean

MIN_WIDTH = 4.0
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’._+\-]*")
_TERM_FIXES = (
    (re.compile(r"(?i)(?<![A-Za-z0-9])open\s*a(?![A-Za-z0-9])"), "OpenAI"),
    (re.compile(r"(?i)(?<![A-Za-z0-9])openai(?![A-Za-z0-9])"), "OpenAI"),
    (re.compile(r"(?i)(?<![A-Za-z0-9])chat\s*gpt(?![A-Za-z0-9])"), "ChatGPT"),
    # 历史遗留：旧引擎曾把 chatgpt 切成 cha/tgpt，手工合并后常留下 chaGPT 这种残形
    (re.compile(r"(?i)(?<![A-Za-z0-9])cha\s*gpt(?![A-Za-z0-9])"), "ChatGPT"),
    (re.compile(r"(?i)(?<![A-Za-z0-9])open\s*wrt(?![A-Za-z0-9])"), "OpenWrt"),
    (re.compile(r"(?i)(?<![A-Za-z0-9])w\s*r\s*t(?![A-Za-z0-9])"), "OpenWrt"),
    (re.compile(r"(?i)(?<![A-Za-z0-9])git\s+hub(?![A-Za-z0-9])"), "GitHub"),
    (re.compile(r"(?<![A-Za-z0-9])omp(?![A-Za-z0-9])", re.I), "OMP"),
    (re.compile(r"(?<![A-Za-z0-9])mcp(?![A-Za-z0-9])", re.I), "MCP"),
    (re.compile(r"让\s*[aA]\s*(?=[去来帮给])"), "让AI"),
    (re.compile(r"你的\s*[iI]\s*(?=[就可以能来会])"), "你的AI"),
    # 硬件型号：剪映/Whisper 常把「影石 Link 2 Pro」误听成「萤石的leak2Pro」「影持的立卡2」
    (re.compile(r"(?i)[萤影][石持诗]的?\s*(?:leak|link|liquor|立卡|里克)\s*2\s*(?:pro|por)?"), "影石 Link 2 Pro"),
)


def display_width(text: str) -> float:
    """字幕实际显示宽度：半角英文/数字按 0.5 计，中文全角按 1.0 计。
    按宽度而非字符数排版，才能保证 ChatGPT / session 这类英文词不被误判超长。"""
    return sum(0.5 if ord(c) < 128 else 1.0 for c in text)


# 语气词 / 口水词：剪映「识别字幕」会把「啊 / 呢 / 啦 / 吧 / 呀」原样打进字幕，
# 既拖节奏又白占单行字数。这里统一清掉；「网吧 / 吧台 / 呢喃 / 啦啦队 / 干嘛 / 哎呀」等实词要保护。
_FILLER_CHARS = "啊呢啦吧嘛哦噢额诶嗯呃呀"
_FILLER_KEEP = re.compile(r"(?:网吧|吧台|吧唧|呢喃|呢子|啦啦队|干嘛|好嘛|啊哈|哦豁|嗯哼|阿拉丁|哎呀)")


def strip_fillers(text: str) -> str:
    """删除口语语气词与口水词，避免字幕一闪而过、节奏拖沓。"""
    if not text:
        return text
    kept: Dict[str, str] = {}

    def stash(m) -> str:
        key = f"\ue000{len(kept)}\ue001"
        kept[key] = m.group(0)
        return key

    text = _FILLER_KEEP.sub(stash, text)
    text = re.sub(f"[{_FILLER_CHARS}]", "", text)
    text = re.sub(r"是了(?=[用把在])", "是", text)  # 「而是了用电脑」这类识别赘字
    text = re.sub(r"如果了(?=[你我他她它])", "如果", text)
    text = re.sub(r"(?<=[地址门槛系统])了$", "", text)
    for key, val in kept.items():
        text = text.replace(key, val)
    return text

def normalize_terms(text: str) -> str:
    """专有名词正字：chatgpt → ChatGPT，open a / openai → OpenAI。"""
    for pattern, repl in _TERM_FIXES:
        text = pattern.sub(repl, text)
    return text


def _protected_spans(text: str) -> List[Tuple[int, int]]:
    """英文/数字单词占用的字符区间，切分时严禁从此区间内部切断。"""
    return [(m.start(), m.end()) for m in _ASCII_TOKEN_RE.finditer(text)]


_CLITIC_HEADS = "的得地了着吗呢吧啊"
_ZH_COMPOUNDS = re.compile(
    r"(?:分享|系统|可以|安装|智能体|插件|主题|报错|分析|操作|示例|打开|博客|文章|开源|项目|"
    r"地址|配置|日常|场景|排查|负载|连接|同样|大家|自己|一定|东西|实现|已经|软件|视频|"
    r"电脑|手机|工具|工作流|自动化|提示词|摄像头|路由器|磁盘|情况|新手|小白|门槛|程度|的话)"
)


def _choose_cut(text: str, spans: List[Tuple[int, int]]) -> Optional[int]:
    """挑选切点：不落在英文单词内部；尽量不劈开常见中文双字/三字词；按显示宽度求最均衡；尽量不把「的/了」这类虚词甩到下一行开头。"""
    n = len(text)
    legal = [i for i in range(1, n) if not any(s < i < e for s, e in spans)]
    if not legal:
        return None
    balanced = [i for i in legal if i >= 3 and n - i >= 3]
    pool = balanced or legal
    spaced = [i for i in pool if text[i - 1] == " " or text[i] == " "]
    pool = spaced or pool
    half = display_width(text) / 2
    zh_spans = [(m.start(), m.end()) for m in _ZH_COMPOUNDS.finditer(text)]

    def score(i: int) -> Tuple[float, int]:
        penalty = 1.5 if text[i] in _CLITIC_HEADS else 0.0
        if any(s < i < e for s, e in zh_spans):
            penalty += 4.0
        return (abs(display_width(text[:i]) - half) + penalty, -i)

    return min(pool, key=score)

def _split_long_text(text: str, max_width: float) -> List[str]:
    """把超宽文本切成 <= max_width 的片段，绝不从英文单词中间切断。"""
    text = text.strip()
    if display_width(text) <= max_width:
        return [text]
    cut = _choose_cut(text, _protected_spans(text))
    if cut is None:
        return [text]  # 宁可整句略超宽，也不把专有名词劈成两半
    left, right = text[:cut].strip(), text[cut:].strip()
    if not left or not right:
        return [text]
    return _split_long_text(left, max_width) + _split_long_text(right, max_width)


def _merge_short_slices(texts: List[str], max_width: float) -> List[str]:
    """合并寡词行（宽度不足 MIN_WIDTH），杜绝 2~4 字一闪而过。"""
    merged: List[str] = []
    for t in texts:
        if (merged
                and (display_width(merged[-1]) < MIN_WIDTH or display_width(t) < MIN_WIDTH)
                and display_width(merged[-1]) + display_width(t) <= max_width + 2):
            merged[-1] += t
        else:
            merged.append(t)
    return merged


def split_into_single_line_slices(raw_text: str, start: int, duration: int, max_len: int = 10) -> List[Dict[str, Any]]:
    """
    将长句子按气口和连词细切为 5~10 字宽的单行短句切片（原文守恒、单行顺次滚动、时间轴比例分配）
    """
    clean = normalize_terms(strip_fillers(raw_text.strip().rstrip("，。！？,.!? ")))
    if not clean:
        return []

    clean_pure = clean.replace("\n", "").replace("，", "").replace("。", "").strip()
    if display_width(clean_pure) <= max_len:
        return [{"text": clean_pure, "start": start, "duration": duration}]

    delimiters = ["，", "对", "或者", "在", "包括", "事实上", "目前", "真正", "最顶尖", "最多大概", "其实", "也就是说", "因此", "但是"]
    parts = [clean]
    for d in delimiters:
        new_parts = []
        for p in parts:
            if display_width(p.replace("\n", "").replace("，", "").replace(" ", "")) > max_len and d in p:
                idx = p.find(d)
                if 3 <= idx <= len(p) - 3:
                    new_parts.append(p[:idx])
                    new_parts.append(p[idx:])
                else:
                    new_parts.append(p)
            else:
                new_parts.append(p)
        parts = new_parts

    final_texts = []
    for p in parts:
        p_clean = p.replace("\n", "").replace("，", "").strip()
        if not p_clean:
            continue
        if display_width(p_clean) <= max_len:
            final_texts.append(p_clean)
        else:
            final_texts.extend(_split_long_text(p_clean, max_len))

    final_texts = _merge_short_slices(final_texts, max_len)

    if not final_texts:
        return [{"text": clean_pure, "start": start, "duration": duration}]

    total_width = sum(display_width(t) for t in final_texts) or 1.0
    slices = []
    cur_start = start
    for idx, t in enumerate(final_texts):
        if idx == len(final_texts) - 1:
            cur_dur = (start + duration) - cur_start
        else:
            cur_dur = int(duration * (display_width(t) / total_width))
        slices.append({
            "text": t,
            "start": cur_start,
            "duration": cur_dur
        })
        cur_start += cur_dur

    return slices


def _norm_for_match(text: str) -> str:
    return re.sub(r"[\s，。！？,.!?、]", "", text)


def _match_key(text: str) -> str:
    """还原匹配用的归一化键：先做正字与口水词清洗，再比对，
    这样「open a的官方」与「OpenAI的官方」、「我们呃去」与「我们去」都能对上。"""
    return _norm_for_match(normalize_terms(strip_fillers(text)))


def remerge_segments_to_lines(
    sub_segs: List[Dict[str, Any]],
    mid_to_mat: Dict[str, Dict[str, Any]],
    lines: List[str]
) -> Tuple[Optional[List[Dict[str, Any]]], bool]:
    """
    把已被切碎的字幕切片按原始台词重新合并回整句，恢复原文与原始时间跨度。
    任何一句对不上就返回 ok=False —— 绝不写入半成品字幕。
    """
    merged: List[Dict[str, Any]] = []
    buf_text: List[str] = []
    buf_segs: List[Dict[str, Any]] = []
    cursor = 0
    for seg in sub_segs:
        mat = mid_to_mat.get(seg.get("material_id"))
        if not mat:
            continue
        try:
            txt = json.loads(mat.get("content", "{}")).get("text", "")
        except Exception:
            txt = ""
        buf_text.append(_match_key(txt))
        buf_segs.append(seg)
        if cursor < len(lines) and "".join(buf_text) == _match_key(lines[cursor]):
            first, last = buf_segs[0], buf_segs[-1]
            st = first["target_timerange"]["start"]
            end = last["target_timerange"]["start"] + last["target_timerange"]["duration"]
            merged.append({
                "id": first["id"],
                "material_id": first["material_id"],
                "target_timerange": {"start": st, "duration": end - st},
                "_text": lines[cursor],
            })
            buf_text, buf_segs = [], []
            cursor += 1
    if cursor != len(lines):
        return None, False
    return merged, True


def _segment_text(seg: Dict[str, Any], mid_to_mat: Dict[str, Dict[str, Any]]) -> str:
    if seg.get("_text") is not None:
        return seg["_text"]
    mat = mid_to_mat.get(seg.get("material_id"))
    if not mat:
        return ""
    try:
        return json.loads(mat.get("content", "{}")).get("text", "")
    except Exception:
        return ""


def merge_short_segments(
    sub_segs: List[Dict[str, Any]],
    mid_to_mat: Dict[str, Dict[str, Any]],
    max_len: int = 10
) -> List[Dict[str, Any]]:
    """把 1~4 字的碎句并入下一句（顺带吞掉中间空档），杜绝寡词单独一闪而过。"""
    merged: List[Dict[str, Any]] = []
    carry: Optional[Tuple[str, int, int, Dict[str, Any]]] = None  # (text, start, duration, seg)

    def flush_carry(text: str, start: int, dur: int, seg: Dict[str, Any]) -> None:
        item = dict(seg)
        item["target_timerange"] = {"start": start, "duration": dur}
        item["_text"] = text
        merged.append(item)

    for seg in sub_segs:
        text = strip_fillers(_segment_text(seg, mid_to_mat)).strip()
        tr = seg["target_timerange"]
        start, dur = tr["start"], tr["duration"]
        if carry:
            gap_us = start - (carry[1] + carry[2])
            if display_width(carry[0]) + display_width(text) <= max_len + 2 or gap_us <= 1_500_000:
                text = carry[0] + text
                start, dur = carry[1], start + dur - carry[1]
            else:
                # 合并会跨过长停顿，宁可保留这句短句，也不硬拼
                flush_carry(*carry)
            carry = None
        if not text:
            continue
        if display_width(text) < MIN_WIDTH:
            carry = (text, start, dur, seg)
            continue
        flush_carry(text, start, dur, seg)

    if carry:
        carry_text, carry_start, carry_dur, carry_seg = carry
        if merged and display_width(merged[-1]["_text"]) + display_width(carry_text) <= max_len + 2:
            merged[-1]["_text"] += carry_text
        else:
            flush_carry(carry_text, carry_start, carry_dur, carry_seg)
    return merged


_PROPER_NOUNS = ("影石 Link 2 Pro", "ChatGPT", "OpenAI", "OpenWrt", "GitHub", "OMP", "MCP", "AI", "dqtx.cc", "FocuSee", "OpenFilm")
_STRONG_KEYWORDS = (
    "影石", "智能体", "剪映", "摄像头", "字幕", "口播", "剪辑", "封装",
    "概念", "审美", "标准", "评论区", "开拍", "桌面", "识别", "校正",
    "工作流", "自动化", "提示词", "智能字幕", "开源项目", "两个概念",
    "第二步", "最大的好处", "非常方便", "非常麻烦", "MCP",
    "开源", "报错", "排查", "配置", "插件", "磁盘", "负载", "博客", "路由器",
)
_NORMAL_KEYWORDS = (
    "拍摄", "电脑", "手机", "视频", "操作", "效果", "方便", "麻烦",
    "缺点", "好处", "画面", "分享", "日常", "第一个", "基本上", "想要",
    "自动", "导入", "感受", "审美", "标准", "摄像头", "画面", "安装", "主题",
)

def extract_highlight_keyword(text: str) -> Tuple[Optional[str], int]:
    """提取核心重点词，返回 (词, 强度)。

    强度 2 = 强重点（句内亮黄放大 + 该行底色 + 动效/音效候选）
    强度 1 = 普通重点（仅句内亮黄放大）
    旧版写死了一组特定视频的业务词，换一支片子就 0 命中；这里改成
    「专有名词 > 英文/型号 token > 通用工具方法论词库 > 通用场景词库」四级兜底。
    """
    for noun in _PROPER_NOUNS:
        if noun in text:
            return noun, 2
    tokens = [m.group(0) for m in _ASCII_TOKEN_RE.finditer(text) if len(m.group(0)) >= 2]
    if tokens:
        return max(tokens, key=len), 2
    for word in sorted(_STRONG_KEYWORDS, key=len, reverse=True):
        if word in text:
            return word, 2
    for word in sorted(_NORMAL_KEYWORDS, key=len, reverse=True):
        if word in text:
            return word, 1
    return None, 0


def _probe_audio_duration_us(path: Path) -> int:
    """读取音效真实时长（微秒），ffprobe 不可用时安全退回 0.8s。"""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=3)
        sec = float((r.stdout or "").strip())
        if sec > 0:
            return int(sec * 1_000_000)
    except Exception:
        pass
    return 800000


def pick_cue_indices(plan: List[Dict[str, Any]], target: int = 7,
                     min_gap: int = 3) -> Dict[int, Tuple[str, str, str, float]]:
    """按「强重点词 + 时间均匀分桶」挑 5~8 个动效/音效卡点。

    旧版把 cue 写死在切片 0/1/4/6/8/13/15/21/25，全部挤在全片前 1/3（前 39 秒），
    后面 60 多秒一点动静都没有 —— 这正是用户「动画音效好像都没有」的根因。
    """
    n = len(plan)
    if not n:
        return {}
    anim_keys = ["type", "whoosh", "pop", "thud", "zoom", "sunrise", "flip"]
    sfx_lib = [
        ("keyboard/type-fast.mp3", "打字声", 0.78),
        ("transition/whoosh.mp3", "极速破风", 0.75),
        ("feedback/notification-pop.mp3", "气泡弹出", 0.80),
        ("impact/drop-thud.mp3", "低音定格", 0.78),
        ("feedback/error-tone.mp3", "警报反差", 0.75),
        ("container/card-flip.mp3", "翻牌展开", 0.78),
        ("feedback/success-chime.mp3", "金币叮", 0.78),
        ("impact/brand-stamp.mp3", "盖章定调", 0.78),
        ("magic/sparkle.mp3", "星光收尾", 0.78),
    ]
    chosen: List[int] = []
    last = -min_gap * 10
    for bucket in range(target):
        lo, hi = n * bucket // target, n * (bucket + 1) // target
        window = plan[lo:hi]
        cand = [p for p in window if p["strength"] >= 2 and p["seg_idx"] - last >= min_gap]
        if not cand:
            cand = [p for p in window if p["kw"] and p["seg_idx"] - last >= min_gap]
        if not cand:
            cand = [p for p in window if p["seg_idx"] - last >= min_gap]
        if not cand:
            cand = list(window)
        if not cand:
            continue
        pick = cand[len(cand) // 2]
        chosen.append(pick["seg_idx"])
        last = pick["seg_idx"]
    out: Dict[int, Tuple[str, str, str, float]] = {}
    for i, idx in enumerate(chosen):
        rel, tag, vol = sfx_lib[i % len(sfx_lib)]
        out[idx] = (anim_keys[i % len(anim_keys)], rel, tag, vol)
    return out


def detect_source_silences(video_path: Path, noise_db: str = "-34dB", min_dur: float = 0.28) -> List[Tuple[int, int]]:
    """用 ffmpeg silencedetect 探测主视频静音气口区间（微秒）。"""
    if not video_path.exists():
        return []
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(video_path),
             "-af", f"silencedetect=noise={noise_db}:d={min_dur}", "-f", "null", "-"],
            capture_output=True, text=True, timeout=60
        )
    except Exception:
        return []
    silences: List[Tuple[int, int]] = []
    cur_start: Optional[float] = None
    for line in (r.stderr or "").splitlines():
        m1 = re.search(r"silence_start:\s*([0-9.]+)", line)
        if m1:
            cur_start = float(m1.group(1))
            continue
        m2 = re.search(r"silence_end:\s*([0-9.]+)", line)
        if m2 and cur_start is not None:
            end_s = float(m2.group(1))
            if end_s > cur_start:
                silences.append((int(round(cur_start * 1_000_000)), int(round(end_s * 1_000_000))))
            cur_start = None
    return silences


def compute_timeline_cuts(
    video_segs: List[Dict[str, Any]],
    source_silences: List[Tuple[int, int]],
    plan: List[Dict[str, Any]],
    min_silence_us: int = 300_000,
    keep_pad_us: int = 50_000,
) -> List[Tuple[int, int]]:
    """将源视频静音区间投影到当前时间轴，生成不损伤台词的剪气口区间（幂等：已剪过的 100ms 停顿不会再剪）。"""
    raw_cuts: List[Tuple[int, int]] = []
    for vseg in video_segs:
        ttr = vseg.get("target_timerange") or {}
        str_r = vseg.get("source_timerange") or {}
        t0 = int(ttr.get("start", 0))
        tdur = int(ttr.get("duration", 0))
        s0 = int(str_r.get("start", 0))
        sdur = int(str_r.get("duration", tdur))
        if tdur <= 0 or sdur <= 0:
            continue
        speed = float(vseg.get("speed") or 1.0)
        s1 = s0 + sdur
        for ss, se in source_silences:
            if ss >= s1 or se <= s0:
                continue
            ts = t0 + int(round((max(ss, s0) - s0) / speed))
            te = t0 + int(round((min(se, s1) - s0) / speed))
            if te - ts >= min_silence_us:
                cs, ce = ts + keep_pad_us, te - keep_pad_us
                if ce - cs >= 150_000:
                    raw_cuts.append((cs, ce))
    if not raw_cuts:
        return []
    raw_cuts.sort()
    merged: List[Tuple[int, int]] = []
    for cs, ce in raw_cuts:
        if merged and cs <= merged[-1][1] + 33_333:
            merged[-1] = (merged[-1][0], max(merged[-1][1], ce))
        else:
            merged.append((cs, ce))
    # 安全校验：确保任何一条字幕切片被裁剪后仍保留 >= 200ms 展示时长
    safe_cuts: List[Tuple[int, int]] = []
    for cs, ce in merged:
        ok = True
        for item in plan:
            ps = item["start"]
            pe = ps + item["duration"]
            ov = max(0, min(ce, pe) - max(cs, ps))
            if ov > 0 and (item["duration"] - ov) < 200_000:
                ok = False
                break
        if ok:
            safe_cuts.append((cs, ce))
    return safe_cuts


def _clone_extra_refs(data: Dict[str, Any], old_refs: List[str]) -> List[str]:
    """为切分出的新视频片段深拷贝 extra_material_refs 关联素材，避免多段共享同一 ID 冲突。"""
    if not old_refs:
        return []
    mats = data.get("materials") or {}
    id_map: Dict[str, Tuple[List[Any], Dict[str, Any]]] = {}
    for mlist in mats.values():
        if isinstance(mlist, list):
            for obj in mlist:
                if isinstance(obj, dict) and obj.get("id") in old_refs:
                    id_map[obj["id"]] = (mlist, obj)
    new_refs: List[str] = []
    for rid in old_refs:
        if rid in id_map:
            mlist, orig = id_map[rid]
            cloned = copy.deepcopy(orig)
            new_id = str(uuid.uuid4()).upper()
            cloned["id"] = new_id
            mlist.append(cloned)
            new_refs.append(new_id)
        else:
            new_refs.append(rid)
    return new_refs


def _map_time(t: int, cuts: List[Tuple[int, int]]) -> int:
    removed = 0
    for cs, ce in cuts:
        if t <= cs:
            break
        removed += min(t, ce) - cs
    return t - removed


def _split_segment_by_cuts(
    seg: Dict[str, Any],
    cuts: List[Tuple[int, int]],
    data: Dict[str, Any],
    clone_refs: bool = True,
) -> List[Dict[str, Any]]:
    """将一个时间轴片段按 cuts 切分为保留子段，并同步更新 target_timerange 与 source_timerange。"""
    ttr = seg.get("target_timerange") or {}
    t0 = int(ttr.get("start", 0))
    tdur = int(ttr.get("duration", 0))
    t1 = t0 + tdur
    if tdur <= 0:
        return []
    str_r = seg.get("source_timerange")
    speed = float(seg.get("speed") or 1.0)

    pieces: List[Tuple[int, int]] = []
    cur = t0
    for cs, ce in cuts:
        if ce <= cur:
            continue
        if cs >= t1:
            break
        if cs > cur:
            pieces.append((cur, min(cs, t1)))
        cur = max(cur, ce)
    if cur < t1:
        pieces.append((cur, t1))

    out: List[Dict[str, Any]] = []
    for idx, (a, b) in enumerate(pieces):
        if b - a < 33_333:  # 小于 1 帧(30fps)丢弃防异常
            continue
        new_seg = copy.deepcopy(seg)
        if idx > 0 or len(pieces) > 1:
            new_seg["id"] = str(uuid.uuid4()).upper()
            if clone_refs and idx > 0:
                new_seg["extra_material_refs"] = _clone_extra_refs(data, seg.get("extra_material_refs", []))
        new_st = _map_time(a, cuts)
        new_dur = _map_time(b, cuts) - new_st
        new_seg["target_timerange"] = {"start": new_st, "duration": new_dur}
        if isinstance(str_r, dict):
            s0 = int(str_r.get("start", 0))
            new_s0 = s0 + int(round((a - t0) * speed))
            new_sdur = int(round(new_dur * speed))
            new_seg["source_timerange"] = {"start": new_s0, "duration": new_sdur}
        out.append(new_seg)
    return out


def apply_cuts_to_draft(
    data: Dict[str, Any],
    cuts: List[Tuple[int, int]],
    plan: List[Dict[str, Any]],
    text_track: Dict[str, Any],
) -> int:
    """将剪气口区间同步应用到视频轨、辅助轨及字幕计划，返回累计剪掉微秒数。"""
    if not cuts:
        return 0
    for tr in data.get("tracks", []):
        if tr is text_track or tr.get("name") == SFX_TRACK_NAME:
            continue
        segs = tr.get("segments")
        if not segs:
            continue
        new_segs: List[Dict[str, Any]] = []
        for s in segs:
            new_segs.extend(_split_segment_by_cuts(s, cuts, data, clone_refs=(tr.get("type") == "video")))
        tr["segments"] = new_segs
    for item in plan:
        st = item["start"]
        en = st + item["duration"]
        new_st = _map_time(st, cuts)
        new_en = _map_time(en, cuts)
        item["start"] = new_st
        item["duration"] = max(100_000, new_en - new_st)
    return sum(ce - cs for cs, ce in cuts)


def execute_one_click_optimization(
    draft_name_or_path: Optional[str] = None,
    is_vertical: Optional[bool] = None,
    restore_lines: Optional[List[str]] = None,
    trim_silence: bool = True,
) -> Dict[str, Any]:
    """
    一键极速执行全套字幕优化闭环（含自动剪气口 + 横竖屏自适配 + 字幕样式 + 动效音效 + +7dB）
    """
    start_ts = time.time()

    # 1. 定位草稿目录
    if draft_name_or_path:
        p = Path(draft_name_or_path)
        draft_dir = p if p.is_dir() else DRAFT_ROOT / draft_name_or_path
    else:
        draft_dir = get_latest_draft_dir()

    if not draft_dir.exists():
        return {"status": "error", "message": f"草稿不存在: {draft_dir}"}

    draft_name = draft_dir.name
    print(f"🚀 开始极速优化剪映草稿: 【{draft_name}】...")

    # 2. UI 自动化释放剪映内存锁（必须确认回到主页且 .locked 消失，避免剪映退出时用内存旧状态覆盖磁盘）
    from pyJianYingDraft.jianying_controller import JianyingController, ControlFinder
    ctl = None
    try:
        ctl = JianyingController(keep_topmost=True)
        if ctl.app_status == "edit":
            btns = [c for c in ctl.app.GetChildren() if c.ClassName == "TitleBarButton"]
            if len(btns) >= 3:
                btns[2].Click(simulateMove=False)
            for _ in range(20):
                time.sleep(0.5)
                try:
                    ctl = JianyingController(keep_topmost=False)
                except Exception:
                    continue
                if ctl.app_status == "home" and not (draft_dir / ".locked").exists():
                    break
        else:
            ctl.release_topmost()
    except Exception:
        pass

    if (draft_dir / ".locked").exists():
        return {"status": "error", "message": f"草稿【{draft_name}】仍在剪映中打开(.locked存在)，请先退出该草稿回到剪映主页后再运行，避免修改被覆盖。"}

    # 3. 解密草稿 JSON
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([str(JY_DRAFTC), "-dc", str(draft_dir), "-o", td, "--jy-dir", str(JY_INSTALL)], capture_output=True, check=True)
        json_file = Path(td) / "draft_content.json"
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 4. 人声音量增益 +7.0 dB（覆盖全部视频主片段）
        video_track = next((tr for tr in data["tracks"] if tr.get("type") == "video" and tr.get("segments")), None)
        if video_track and video_track["segments"]:
            for v_seg in video_track["segments"]:
                v_seg["volume"] = 2.2387211  # +7.0 dB
                v_seg["last_nonzero_volume"] = 2.2387211
        # 5. 基础字幕轨处理
        text_track = next((tr for tr in data["tracks"] if tr.get("type") == "text"), None)
        if not text_track or not text_track.get("segments"):
            return {"status": "error", "message": "该草稿中未找到字幕轨道，请先在剪映中识别或导入字幕！"}

        sub_segs = text_track["segments"]
        original_text_idx = data["tracks"].index(text_track)
        materials_texts = data.get("materials", {}).get("texts", [])
        mid_to_mat = {m["id"]: m for m in materials_texts}

        # 5.1 可选：按原始台词还原已被切碎的草稿（保证重跑幂等，英文词不被二次劈开）
        if restore_lines:
            merged_segs, ok = remerge_segments_to_lines(sub_segs, mid_to_mat, restore_lines)
            if not ok:
                return {"status": "error", "message": "按原文还原失败：切片文本与原始台词对不上，已中止写入。"}
            sub_segs = merged_segs

        sub_segs = merge_short_segments(sub_segs, mid_to_mat)

        if is_vertical is None:
            canvas = data.get("canvas_config") or {}
            cw, ch = canvas.get("width", 1080), canvas.get("height", 1920)
            is_vertical = (ch >= cw)
        base_size = 13.0 if is_vertical else 7.0
        highlight_size = 16.5 if is_vertical else 9.0
        y_pos = -0.42 if is_vertical else -0.75  # 竖屏锁定 -0.42 安全区，横屏 -0.75 贴近底部
        # 准备动画与音效
        material_animations = []
        materials_audios = [a for a in data["materials"].get("audios", []) if not a.get("name", "").startswith("留存音效:")]
        sfx_segments = []

        # 复用剪映已补全的动画模板（含本机 effect 缓存 path），保证首次打开即能渲染
        anim_tpl: Dict[str, Dict[str, Any]] = {}
        for a in data["materials"].get("material_animations", []):
            for an in a.get("animations", []):
                if an.get("id") and an.get("path"):
                    anim_tpl[str(an["id"])] = an

        # 阶段一：先算出全部单行切片及其重点词，动效卡点才能按语义 + 全片均匀分布来挑
        plan: List[Dict[str, Any]] = []
        for seg in sub_segs:
            mid = seg["material_id"]
            if mid not in mid_to_mat:
                continue
            m_obj = mid_to_mat[mid]
            c_dict = json.loads(m_obj.get("content", "{}"))
            raw_t = seg.get("_text") or c_dict.get("text", "")
            st = seg["target_timerange"]["start"]
            dur = seg["target_timerange"]["duration"]
            # 核心铁律：单行顺次滚动（5~10字短语切片，绝对杜绝双行堆叠与左右出界裁切）
            for s_info in split_into_single_line_slices(raw_t, st, dur, max_len=10):
                txt = s_info["text"]
                kw, strength = extract_highlight_keyword(txt)
                plan.append({
                    "text": txt,
                    "start": s_info["start"],
                    "duration": s_info["duration"],
                    "kw": kw,
                    "strength": strength,
                    "seg_idx": len(plan),
                })

        # 阶段 1.5：自动剪气口（Jump-Cut：裁剪 >=0.30s 静音停顿，保留 100ms 自然呼吸）
        cuts_applied: List[Tuple[int, int]] = []
        trimmed_us = 0
        if trim_silence and video_track and video_track.get("segments"):
            videos_mat = data.get("materials", {}).get("videos") or []
            v_path = Path(videos_mat[0]["path"]) if videos_mat and videos_mat[0].get("path") else None
            if v_path and v_path.exists():
                src_silences = detect_source_silences(v_path)
                cuts_applied = compute_timeline_cuts(video_track["segments"], src_silences, plan)
                if cuts_applied:
                    trimmed_us = apply_cuts_to_draft(data, cuts_applied, plan, text_track)

        # 阶段二：7 个时间桶各挑 1 个强重点词，动效 + 音效覆盖全片（基于剪气口后新时码）
        cue_indices = pick_cue_indices(plan, target=7)

        new_sub_segments = []
        new_materials_texts = []

        for item in plan:
            slice_text = item["text"]
            slice_st = item["start"]
            slice_dur = item["duration"]
            seg_idx = item["seg_idx"]
            kw, strength = item["kw"], item["strength"]
            mat_id = str(uuid.uuid4()).upper()

            base_style = {
                "fill": {"alpha": 1.0, "content": {"render_type": "solid", "solid": {"alpha": 1.0, "color": [1.0, 1.0, 1.0]}}},
                "font": {"id": YANSONG_ID, "path": YANSONG_PATH},
                "size": base_size,
                "shadows": SHADOW_SPEC,
                "strokes": STROKE_SPEC,
                "range": [0, len(slice_text)]
            }
            styles = [base_style]

            if kw and kw in slice_text:
                k_start = slice_text.find(kw)
                k_end = k_start + len(kw)
                styles.append({
                    "fill": {"alpha": 1.0, "content": {"render_type": "solid", "solid": {"alpha": 1.0, "color": [1.0, 0.88, 0.15]}}},
                    "font": {"id": YANSONG_ID, "path": YANSONG_PATH},
                    "size": highlight_size,
                    "bold": True,
                    "shadows": SHADOW_SPEC,
                    "strokes": STROKE_SPEC,
                    "range": [k_start, k_end]
                })

            new_c_dict = {"text": slice_text, "styles": styles}
            new_m_obj = {
                "id": mat_id,
                "type": "text",
                "content": json.dumps(new_c_dict, ensure_ascii=False),
                "font_title": "研宋体",
                "font_id": "4010355",
                "font_resource_id": YANSONG_ID,
                "font_path": YANSONG_PATH,
                "font_size": base_size,
                "border_width": STROKE_WIDTH,
                "border_color": "#000000",
                "border_alpha": STROKE_ALPHA,
                "has_shadow": True,
                "shadow_alpha": 0.6,
                "shadow_color": "#000000",
                "shadow_diffuse": 0.010031185,
                "shadow_distance": 6.0,
                "shadow_angle": -60.0,
                "background_style": 0,
                "check_flag": CHECK_FLAG
            }
            # 强重点词所在行加底色：剪映要求 background_style=1 且 check_flag |= 16，缺一不渲染
            if strength >= 2:
                new_m_obj.update({
                    "background_style": 1,
                    "background_color": "#181818",
                    "background_alpha": 0.85,
                    "background_round_radius": 0.20,
                    "background_height": 0.14,
                    "background_width": 0.14,
                    "background_horizontal_offset": 0.0,
                    "background_vertical_offset": 0.0,
                    "check_flag": CHECK_FLAG | 16,   # 47 | 16 = 63
                })
            new_materials_texts.append(new_m_obj)

            extra_refs = []
            if seg_idx in cue_indices:
                anim_key, sfx_rel, sfx_tag, sfx_vol = cue_indices[seg_idx]
                anim_info = ANIM_LIB[anim_key]
                a_mat_id = str(uuid.uuid4()).upper()
                anim = dict(anim_tpl.get(anim_info["id"], {}))
                anim.update({
                    "id": anim_info["id"],
                    "type": "in",
                    "start": 0,
                    "duration": anim_info["dur"],
                    "resource_id": anim_info["res"],
                    "name": anim_info["name"]
                })
                material_animations.append({
                    "animations": [anim],
                    "id": a_mat_id,
                    "type": "sticker_animation"
                })
                extra_refs.append(a_mat_id)

                sfx_file = SFX_DIR / sfx_rel
                if sfx_file.exists():
                    sfx_id = str(uuid.uuid4()).upper()
                    sfx_total = _probe_audio_duration_us(sfx_file)
                    # 字段一次写全：不要依赖「剪映打开后再补全」，首次加载就要能出声
                    materials_audios.append({
                        "id": sfx_id,
                        "type": "none",
                        "path": str(sfx_file).replace("\\", "/"),
                        "name": f"留存音效:{sfx_tag}",
                        "duration": sfx_total,
                        "check_flag": 1,
                        "wave_points": [],
                        "source_from": "",
                        "local_material_id": "",
                    })
                    sfx_dur = min(slice_dur, sfx_total, 800000)
                    sfx_segments.append({
                        "id": str(uuid.uuid4()).upper(),
                        "material_id": sfx_id,
                        "target_timerange": {"start": slice_st, "duration": sfx_dur},
                        "source_timerange": {"start": 0, "duration": sfx_dur},
                        "speed": 1.0,
                        "volume": sfx_vol,
                        "visible": True,
                    })

            new_seg_id = str(uuid.uuid4()).upper()
            new_sub_segments.append({
                "id": new_seg_id,
                "material_id": mat_id,
                "target_timerange": {"start": slice_st, "duration": slice_dur},
                "source_timerange": {"start": 0, "duration": slice_dur},
                "speed": 1.0,
                "volume": 1.0,
                "clip": {"transform": {"x": 0.0, "y": y_pos}},
                "extra_material_refs": extra_refs
            })

        text_track["segments"] = new_sub_segments
        data["materials"]["texts"] = new_materials_texts
        data["materials"]["audios"] = materials_audios

        # 铁律：除字幕轨与旧的留存音效轨外，其余轨道（画中画、贴纸、特效、BGM）必须原样保留。
        # 早期版本用 [video_track, text_track] 重建轨道列表，会把用户加的画中画整条删掉。
        final_tracks = [
            tr for tr in data["tracks"]
            if tr is not text_track and tr.get("name") != SFX_TRACK_NAME
        ]
        final_tracks.insert(min(original_text_idx, len(final_tracks)), text_track)

        if sfx_segments:
            final_tracks.append({
                "id": str(uuid.uuid4()).upper(),
                "name": SFX_TRACK_NAME,
                "type": "audio",
                "segments": sfx_segments
            })

        # 动画素材按引用保留：只丢弃已无人引用的旧字幕动画，避免把画中画/贴纸的动画一起清空
        kept_refs = set()
        for tr in final_tracks:
            if tr is text_track:
                continue
            for s in tr.get("segments", []):
                kept_refs.update(s.get("extra_material_refs", []))
        kept_anims = [
            a for a in data["materials"].get("material_animations", [])
            if a.get("id") in kept_refs
        ]
        data["materials"]["material_animations"] = kept_anims + material_animations
        data["tracks"] = final_tracks
        max_end = max(
            (s["target_timerange"]["start"] + s["target_timerange"]["duration"]
             for tr in final_tracks for s in tr.get("segments", []) if isinstance(s.get("target_timerange"), dict)),
            default=data.get("duration", 0),
        )
        if max_end > 0:
            data["duration"] = max_end

        # 7. 加密并多副本同步覆盖
        content_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        with open(json_file, "wb") as f:
            f.write(content_bytes)
        if (Path(td) / "draft_content.json.bak").exists():
            with open(Path(td) / "draft_content.json.bak", "wb") as f:
                f.write(content_bytes)
        if (Path(td) / "template-2.tmp").exists():
            with open(Path(td) / "template-2.tmp", "wb") as f:
                f.write(content_bytes)

        enc_out = Path(td) / "enc"
        subprocess.run([str(JY_DRAFTC), "-ec", td, "-o", str(enc_out), "--jy-dir", str(JY_INSTALL)], capture_output=True, check=True)

        shutil.copy2(enc_out / "draft_content.json", draft_dir / "draft_content.json")
        if (draft_dir / "draft_content.json.bak").exists():
            shutil.copy2(enc_out / "draft_content.json", draft_dir / "draft_content.json.bak")
        if (draft_dir / "template-2.tmp").exists():
            shutil.copy2(enc_out / "draft_content.json", draft_dir / "template-2.tmp")

    # 8. UI 自动化即时重新打开
    try:
        ctl = JianyingController(keep_topmost=True)
        if ctl.app_status == "home":
            draft_text = ctl.app.TextControl(searchDepth=2, Compare=ControlFinder.desc_matcher(f"HomePageDraftTitle:{draft_name}", exact=True))
            if draft_text.Exists(2):
                btn = draft_text.GetParentControl()
                btn.Click(simulateMove=False)
        ctl.release_topmost()
    except Exception:
        pass

    cost = round(time.time() - start_ts, 2)
    print(f"✨ 极速优化完成！总耗时: {cost} 秒，原工程已在剪映中即刻刷新！")
    return {
        "status": "success",
        "draft_name": draft_name,
        "orientation": "vertical" if is_vertical else "horizontal",
        "base_size": base_size,
        "highlight_size": highlight_size,
        "total_segments": len(plan),
        "silence_cuts": len(cuts_applied),
        "trimmed_seconds": round(trimmed_us / 1_000_000, 2),
        "y_position": y_pos,
        "cost_seconds": cost
    }


def inspect_draft_orientation(draft_name_or_path: Optional[str] = None) -> Dict[str, Any]:
    """只读探测草稿画布与主视频分辨率，供执行前确认横/竖屏。"""
    if draft_name_or_path:
        p = Path(draft_name_or_path)
        draft_dir = p if p.is_dir() else DRAFT_ROOT / draft_name_or_path
    else:
        draft_dir = get_latest_draft_dir()
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([str(JY_DRAFTC), "-dc", str(draft_dir), "-o", td, "--jy-dir", str(JY_INSTALL)], capture_output=True, check=True)
        data = json.loads((Path(td) / "draft_content.json").read_text(encoding="utf-8"))
    canvas = data.get("canvas_config") or {}
    cw, ch = canvas.get("width", 0), canvas.get("height", 0)
    videos = data.get("materials", {}).get("videos") or []
    vw = videos[0].get("width", 0) if videos else 0
    vh = videos[0].get("height", 0) if videos else 0
    detected = "vertical" if ch >= cw else "horizontal"
    return {
        "draft_name": draft_dir.name,
        "canvas": {"width": cw, "height": ch, "ratio": canvas.get("ratio")},
        "video": {"width": vw, "height": vh},
        "detected_orientation": detected,
    }


def main():
    parser = argparse.ArgumentParser(description="剪映口播字幕一键极速优化引擎")
    parser.add_argument("--draft", type=str, default=None, help="草稿名称或路径（默认自动抓取最后编辑的草稿）")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--horizontal", action="store_true", help="按横屏 16:9 排版（字号 7.0/9.0, y=-0.75）")
    group.add_argument("--vertical", action="store_true", help="按竖屏 9:16 排版（字号 13.0/16.5, y=-0.42）")
    parser.add_argument("--probe", action="store_true", help="仅探测草稿画布与视频分辨率，不修改文件")
    parser.add_argument("--no-trim-silence", action="store_true", help="跳过自动剪气口（默认开启自动裁剪 >=0.30s 静音停顿）")
    parser.add_argument("--restore-lines", type=str, default=None,
                        help='原始台词 JSON 文件（{"lines": [...]}）：先把已被切碎的草稿还原成整句，再重新排版')
    args = parser.parse_args()

    if args.probe:
        print(json.dumps(inspect_draft_orientation(args.draft), ensure_ascii=False, indent=2))
        return

    restore_lines = None
    if args.restore_lines:
        with open(args.restore_lines, "r", encoding="utf-8") as f:
            restore_lines = json.load(f)["lines"]

    is_vertical: Optional[bool] = None
    if args.horizontal:
        is_vertical = False
    elif args.vertical:
        is_vertical = True

    res = execute_one_click_optimization(
        draft_name_or_path=args.draft,
        is_vertical=is_vertical,
        restore_lines=restore_lines,
        trim_silence=not args.no_trim_silence,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res.get("status") != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
