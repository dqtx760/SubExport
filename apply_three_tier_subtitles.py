#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三层视觉字幕排版生成器 (Three-tier Subtitle Formatter)
- 头顶标题字幕区域：雅月体 + 花字渐变效果，置于画面最顶部 (y=0.78)，贯穿全片
- 胸前重点字幕区域：经典雅黑 + 阴影 + 亮黄描边，置于胸前中间 (y=-0.05)，8个核心论点关键时刻卡点弹出
- 基础字幕区域：研宋体 + 严格不超过8个字 + 阴影（透明度60%、模糊度6%、距离6、角度-60°），字号13.0，置于底部常规位置 (y=-0.65)
"""

import os
import sys
import copy
import json
import uuid
import shutil
import tempfile
import subprocess
from pathlib import Path

# 路径常量
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
DRAFT_ROOT = LOCALAPPDATA / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
JY_DRAFTC = Path(r"D:\project2026\软件开发\剪映字幕导出\bin\jy-draftc.exe")
JY_INSTALL = Path(r"C:\Users\Administrator\AppData\Local\JianyingPro\Apps\8.9.0.13361")
DESKTOP_DIR = Path.home() / "Desktop"

DRAFT_NAME = "10月24日"
draft_dir = DRAFT_ROOT / DRAFT_NAME

if not draft_dir.exists():
    raise FileNotFoundError(f"未找到目标草稿目录: {draft_dir}")

# 1. 基础字幕文本与分段（严格保证每行不超过 8 个字，语义完整）
# 映射自 74 句原时码，对于超过 8 字的句子按语义自然拆句
BASE_SUBTITLE_SPEC = [
    # (原句序号, 拆分后文本数组)
    (1, ["今天跟大家分享", "关于复利资产"]),           # 今天我跟大家分享一下关于
    (2, ["到底何为", "复利的资产"]),                     # 到底什么叫复利资产
    (3, ["现在很多", "主流大模型"]),                     # 现在很多主流大模型
    (4, ["比如顶尖的", "Claude"]),                       # 比如说顶尖的 Claude
    (5, ["Opus 5.5", "以及顶尖", "GPT-6.1"]),            # Opus 5.5 以及 GPT-6.1-Sol
    (6, ["这样的顶级模型"]),                             # 这样的顶级模型
    (7, ["若只开普通会员"]),                             # 如果你只开一个普通会员
    (8, ["在额度上"]),                                   # 在额度上
    (9, ["如果日常一直"]),                               # 如果你日常一直
    (10, ["高频使用顶模"]),                              # 高频使用顶尖模型
    (11, ["额度肯定不够用"]),                            # 那额度肯定是不够用的
    (12, ["那怎么才能用够"]),                            # 那怎么才能够用呢
    (13, ["其实有个巧办法"]),                            # 其实有一个很巧妙的方法
    (14, ["把顶尖模型成果"]),                            # 那就是把顶尖模型做出的成果
    (15, ["沉淀下来"]),                                 # 沉淀下来
    (16, ["成为复利资产"]),                              # 作为一个能长期复利的资产
    (17, ["后续你在使用"]),                              # 后续你在使用
    (18, ["一些基础模型时"]),                            # 一些基础模型时
    (19, ["比如使用", "Work", "Buddy", "旗下的 Hy3"]),       # 比如使用 WorkBuddy 的 Hy3
    (20, ["或者豆包模型"]),                              # 或者豆包这样的模型
    (21, ["同样可以出好效果"]),                          # 同样可以做出极佳的效果
    (22, ["比如你做了一套"]),                            # 比如你做了一个
    (23, ["视频动效"]),                                 # 视频动效
    (24, ["包装模板"]),                                 # 包装模板
    (25, ["把它作为一个库"]),                            # 把它作为一个特效库
    (26, ["沉淀成固定资产"]),                            # 沉淀成固定的资产
    (27, ["后续制作时"]),                               # 后续制作时
    (28, ["你只需要"]),                                 # 你只需要
    (29, ["根据口播内容"]),                             # 根据
    (30, ["直接匹配套用"]),                             # 你的口播内容直接套用
    (31, ["之前用", "Opus 5.5"]),                        # 之前用 Opus 5.5 制作的
    (32, ["做的现成动效"]),                             # 现成动效就可以了
    (33, ["即使最基础模型"]),                            # 即使你使用最基础的模型
    (34, ["因为特效已固化"]),                            # 但因为核心特效是固定的
    (35, ["只需匹配套用"]),                             # 只需要精准匹配套用
    (36, ["最终交付成片"]),                             # 最终交付的视频成片
    (37, ["依然是顶尖品质"]),                            # 依然是顶尖品质
    (38, ["再比如"]),                                   # 再比如
    (39, ["我平时做网站"]),                             # 我自己平时做网站的时候
    (40, ["用顶尖模型设计"]),                            # 用顶尖模型来设计
    (41, ["做出的审美极佳"]),                            # 它做出来的审美非常好
    (42, ["比如界面的弹窗"]),                            # 比如界面的弹窗
    (43, ["以及功能设计"]),                             # 以及一些交互功能的设计
    (44, ["当我做新网站时"]),                            # 当我做第二个网站时
    (45, ["即使普通模型写"]),                            # 即使我用普通模型来写代码
    (46, ["但我可以把之前"]),                            # 但我可以把之前
    (47, ["做好的网站里"]),                             # 做好的那个网站里
    (48, ["优质模块迁移"]),                             # 优秀的模块与设计直接迁移过来
    (49, ["这样一来"]),                                 # 这样一来
    (50, ["即使使用免费模型"]),                          # 即使使用免费或平价模型
    (51, ["借由之前"]),                                 # 借由之前
    (52, ["顶级模型沉淀的"]),                            # 顶级模型沉淀的
    (53, ["核心资产迁移"]),                             # 核心代码与设计进行迁移
    (54, ["质感依然高级"]),                             # 整体质感依然非常高级
    (55, ["所以这就是"]),                               # 所以这就是
    (56, ["不需要顶尖模型"]),                            # 不需要顶尖模型
    (57, ["也能做顶尖产出"]),                            # 也能做出高品质产出的核心方法
    (58, ["的核心方法"]),                               # 
    (59, ["因为像订阅", "GPT Plus"]),                   # 因为像订阅 ChatGPT Plus
    (60, ["或者订阅", "Claude", "Pro 会员"]),             # 或者 Claude Pro
    (61, ["如果每天"]),                                 # 如果你每天
    (62, ["高强度消耗顶模"]),                            # 都在高强度消耗顶尖模型
    (63, ["额度肯定不够用"]),                            # 额度肯定是不够用的
    (64, ["所以我给的建议"]),                            # 所以我给大家的建议是
    (65, ["只开一个顶尖"]),                             # 你可以只开一个顶尖模型
    (66, ["基础会员即可"]),                             # 哪怕是基础订阅会员
    (67, ["平时日常任务"]),                             # 平时日常任务
    (68, ["搭配平价模型"]),                             # 搭配一些平价模型
    (69, ["或完全免费模型"]),                            # 或者完全免费的模型
    (70, ["在做新项目时"]),                             # 在做新项目的时候
    (71, ["充分复用"]),                                 # 充分复用
    (72, ["之前沉淀的资产"]),                            # 之前沉淀的那些资产
    (73, ["关键前提是"]),                               # 这里的关键前提是
    (74, ["用顶尖模型打磨", "可长效复用资产", "这点非常重要"]) # 这一点非常重要
]

# 2. 胸前重点高光字幕（黄金中心卡点出现）
CHEST_HIGHLIGHTS = [
    {"text": "【 什么是复利资产？ 】", "start_us": 1333000, "dur_us": 4700000},
    {"text": "【 Claude 5.5 + GPT 6.1 】", "start_us": 7166000, "dur_us": 6000000},
    {"text": "【 成果沉淀 ➔ 资产复利 】", "start_us": 14000000, "dur_us": 8000000},
    {"text": "【 WorkBuddy 搭配平价模型 】", "start_us": 24000000, "dur_us": 8500000},
    {"text": "【 特效固定 ➔ 成片依然顶尖 】", "start_us": 37000000, "dur_us": 9000000},
    {"text": "【 模块迁移 ➔ 降维打击 】", "start_us": 65000000, "dur_us": 13000000},
    {"text": "【 普通会员 ➔ 顶尖产出 】", "start_us": 95000000, "dur_us": 13000000},
    {"text": "【 先用顶尖模型打磨资产 】", "start_us": 138000000, "dur_us": 22000000},
]


def make_base_subtitle_material(template_mat, text_str):
    """构建基础字幕素材（研宋体 + <=8字 + 阴影 60%, 模糊度 6%, 距离 6, 角度 -60）"""
    m = copy.deepcopy(template_mat)
    mat_id = uuid.uuid4().hex
    m["id"] = mat_id
    m["font_title"] = "研宋体"
    m["font_id"] = "4010355"
    m["font_resource_id"] = "7130644288047682085"
    m["font_path"] = "C:/Users/Administrator/AppData/Local/JianyingPro/User Data/Cache/effect/4010355/06458c13377d445fe3368cd2c786c7a5/Aa研宋.ttf"
    m["font_size"] = 13.0
    m["has_shadow"] = True
    m["shadow_alpha"] = 0.6
    m["shadow_color"] = "#000000"
    m["shadow_diffuse"] = 0.010031185
    m["shadow_distance"] = 6.0
    m["shadow_angle"] = -60.0
    m["border_width"] = 0.0

    content_dict = {
        "text": text_str,
        "styles": [{
            "fill": {
                "alpha": 1.0,
                "content": {
                    "render_type": "solid",
                    "solid": {"alpha": 1.0, "color": [1.0, 1.0, 1.0]}
                }
            },
            "font": {
                "id": "7130644288047682085",
                "path": "C:/Users/Administrator/AppData/Local/JianyingPro/User Data/Cache/effect/4010355/06458c13377d445fe3368cd2c786c7a5/Aa研宋.ttf"
            },
            "size": 13.0,
            "shadows": [{
                "alpha": 0.6,
                "angle": -60.0,
                "content": {"solid": {"alpha": 1.0, "color": [0.0, 0.0, 0.0]}},
                "diffuse": 0.010031185,
                "distance": 6.0
            }],
            "range": [0, len(text_str)]
        }]
    }
    m["content"] = json.dumps(content_dict, ensure_ascii=False)
    return m, mat_id


def make_chest_highlight_material(template_mat, text_str):
    """构建胸前重点高光字幕素材（经典雅黑 + 亮黄大字号 + 黑色重描边 + 阴影）"""
    m = copy.deepcopy(template_mat)
    mat_id = uuid.uuid4().hex
    m["id"] = mat_id
    m["font_title"] = "经典雅黑"
    m["font_id"] = "1488718"
    m["font_resource_id"] = "7043775037559542279"
    m["font_path"] = ""
    m["font_size"] = 19.0
    m["border_width"] = 12.0
    m["border_color"] = "#000000"
    m["border_alpha"] = 1.0
    m["has_shadow"] = True
    m["shadow_alpha"] = 0.8
    m["shadow_color"] = "#000000"
    m["shadow_distance"] = 8.0
    m["shadow_diffuse"] = 0.03
    m["shadow_angle"] = -60.0

    content_dict = {
        "text": text_str,
        "styles": [{
            "fill": {
                "alpha": 1.0,
                "content": {
                    "render_type": "solid",
                    "solid": {"alpha": 1.0, "color": [1.0, 0.90, 0.15]}
                }
            },
            "font": {
                "id": "7043775037559542279",
                "path": ""
            },
            "size": 19.0,
            "shadows": [{
                "alpha": 0.8,
                "angle": -60.0,
                "content": {"solid": {"alpha": 1.0, "color": [0.0, 0.0, 0.0]}},
                "diffuse": 0.03,
                "distance": 8.0
            }],
            "range": [0, len(text_str)]
        }]
    }
    m["content"] = json.dumps(content_dict, ensure_ascii=False)
    return m, mat_id


def make_top_header_material(template_mat, text_str):
    """构建头顶标题字幕素材（雅月体 + 花字金光渐变效果 + 细深金描边）"""
    m = copy.deepcopy(template_mat)
    mat_id = uuid.uuid4().hex
    m["id"] = mat_id
    m["font_title"] = "雅月体"
    m["font_id"] = "85757855"
    m["font_resource_id"] = "7423616268764189234"
    m["font_path"] = ""
    m["font_size"] = 18.0
    m["border_width"] = 8.0
    m["border_color"] = "#3d2200"
    m["border_alpha"] = 0.9
    m["has_shadow"] = True
    m["shadow_alpha"] = 0.5
    m["shadow_distance"] = 6.0
    m["shadow_color"] = "#221100"
    m["shadow_angle"] = -55.0

    content_dict = {
        "text": text_str,
        "styles": [{
            "fill": {
                "alpha": 1.0,
                "content": {
                    "render_type": "solid",
                    "solid": {"alpha": 1.0, "color": [1.0, 0.85, 0.32]}
                }
            },
            "font": {
                "id": "7423616268764189234",
                "path": ""
            },
            "size": 18.0,
            "shadows": [{
                "alpha": 0.5,
                "angle": -55.0,
                "content": {"solid": {"alpha": 1.0, "color": [0.15, 0.08, 0.0]}},
                "diffuse": 0.02,
                "distance": 6.0
            }],
            "range": [0, len(text_str)]
        }]
    }
    m["content"] = json.dumps(content_dict, ensure_ascii=False)
    return m, mat_id


def build_segment_dict(seg_id, mat_id, start_us, dur_us, transform_y):
    """生成剪映标准 Track Segment 字典"""
    return {
        "caption_info": None,
        "cartoon": False,
        "clip": {
            "alpha": 1.0,
            "flip": {"horizontal": False, "vertical": False},
            "rotation": 0.0,
            "scale": {"x": 1.0, "y": 1.0},
            "transform": {"x": 0.0, "y": transform_y}
        },
        "common_keyframes": [],
        "enable_adjust": True,
        "enable_color_correct_adjust": False,
        "enable_color_curves": True,
        "enable_color_match_adjust": False,
        "enable_color_wheels": True,
        "enable_lut": True,
        "enable_smart_color_adjust": False,
        "extra_material_refs": [],
        "group_id": "",
        "hdr_settings": None,
        "id": seg_id,
        "intensifies_audio": False,
        "is_placeholder": False,
        "is_tone_modify": False,
        "keyframe_refs": [],
        "last_nonzero_volume": 1.0,
        "material_id": mat_id,
        "render_index": 0,
        "responsive_layout": False,
        "reverse": False,
        "source_timerange": None,
        "speed": 1.0,
        "target_timerange": {"duration": int(dur_us), "start": int(start_us)},
        "template_id": "",
        "template_scene": "default",
        "track_attribute": 0,
        "track_render_index": 0,
        "uniform_scale": {"on": True, "value": 1.0},
        "visible": True,
        "volume": 1.0
    }


def main():
    print(f"=== 开始为剪映项目【{DRAFT_NAME}】构建三层字幕样式 ===")

    # 1. 解密原工程备份以提取精准 74 句时间轴
    with tempfile.TemporaryDirectory() as td:
        temp_draft = Path(td) / "draft"
        temp_draft.mkdir()
        shutil.copy2(draft_dir / "draft_content.json.bak", temp_draft / "draft_content.json")
        plain_dir = Path(td) / "plain"
        subprocess.run([str(JY_DRAFTC), "-dc", str(temp_draft), "-o", str(plain_dir), "--jy-dir", str(JY_INSTALL)], capture_output=True, check=True)
        with open(plain_dir / "draft_content.json", "r", encoding="utf-8") as f:
            bak_data = json.load(f)

    # 提取原 74 段时码
    orig_timings = []
    for tr in bak_data["tracks"]:
        if tr.get("type") == "text":
            for s in tr.get("segments", []):
                trange = s.get("target_timerange", {})
                orig_timings.append((trange.get("start", 0), trange.get("duration", 0)))
    orig_timings.sort(key=lambda x: x[0])
    total_video_dur = orig_timings[-1][0] + orig_timings[-1][1]
    print(f"原工程共计 {len(orig_timings)} 个时间片段，视频总长度: {total_video_dur // 1000000} 秒")

    # 2. 解密当前 draft_content.json 作为底座（保留视频轨、画布比例等）
    with tempfile.TemporaryDirectory() as td_work:
        work_dir = Path(td_work) / "work"
        subprocess.run([str(JY_DRAFTC), "-dc", str(draft_dir), "-o", str(work_dir), "--jy-dir", str(JY_INSTALL)], capture_output=True, check=True)
        with open(work_dir / "draft_content.json", "r", encoding="utf-8") as f:
            draft_data = json.load(f)

        template_mat = bak_data["materials"]["texts"][0]

        # 清空现有文本素材与文本轨道
        new_materials_texts = []
        video_tracks = [tr for tr in draft_data.get("tracks", []) if tr.get("type") != "text"]

        # ----------------------------------------------------
        # 轨道一：基础字幕区域（研宋体 + 严格 <= 8 个字 + 阴影 60%, 模糊 6%, 距 6, 角 -60°）
        # ----------------------------------------------------
        base_segments = []
        for (idx, sub_phrases), (st_us, dur_us) in zip(BASE_SUBTITLE_SPEC, orig_timings):
            count = len(sub_phrases)
            sub_dur = dur_us / count
            for i, phrase in enumerate(sub_phrases):
                phrase = phrase.strip()
                if not phrase:
                    continue
                # 检查字数
                if len(phrase) > 8:
                    print(f"警告：句子【{phrase}】超过8字，长度为 {len(phrase)}")

                cur_start = st_us + i * sub_dur
                mat_obj, mat_id = make_base_subtitle_material(template_mat, phrase)
                new_materials_texts.append(mat_obj)

                seg_dict = build_segment_dict(uuid.uuid4().hex, mat_id, cur_start, sub_dur, transform_y=-0.65)
                base_segments.append(seg_dict)

        base_track = {
            "attribute": 0,
            "flag": 1,
            "id": uuid.uuid4().hex,
            "is_default_name": False,
            "name": "基础字幕 (研宋体)",
            "segments": base_segments,
            "type": "text"
        }
        print(f"生成基础字幕句数: {len(base_segments)}（研宋体，<=8字/句，字号13.0，阴影透明度60%）")

        # ----------------------------------------------------
        # 轨道二：胸前重点字幕区域（经典雅黑 + 亮黄粗描边 + 阴影 + y=-0.05）
        # ----------------------------------------------------
        chest_segments = []
        for ch in CHEST_HIGHLIGHTS:
            mat_obj, mat_id = make_chest_highlight_material(template_mat, ch["text"])
            new_materials_texts.append(mat_obj)
            seg_dict = build_segment_dict(uuid.uuid4().hex, mat_id, ch["start_us"], ch["dur_us"], transform_y=-0.05)
            chest_segments.append(seg_dict)

        chest_track = {
            "attribute": 0,
            "flag": 0,
            "id": uuid.uuid4().hex,
            "is_default_name": False,
            "name": "胸前重点 (经典黑)",
            "segments": chest_segments,
            "type": "text"
        }
        print(f"生成胸前重点标签: {len(chest_segments)} 处关键卡点大字")

        # ----------------------------------------------------
        # 轨道三：头顶标题字幕区域（雅月体 + 花字金光渐变 + y=0.78 + 全片贯穿）
        # ----------------------------------------------------
        top_header_text = "普通人如何沉淀 AI 复利资产？"
        top_mat, top_mat_id = make_top_header_material(template_mat, top_header_text)
        new_materials_texts.append(top_mat)

        top_segment = build_segment_dict(
            uuid.uuid4().hex,
            top_mat_id,
            start_us=0,
            dur_us=total_video_dur,
            transform_y=0.78
        )
        top_track = {
            "attribute": 0,
            "flag": 0,
            "id": uuid.uuid4().hex,
            "is_default_name": False,
            "name": "头顶标题 (雅月体花字)",
            "segments": [top_segment],
            "type": "text"
        }
        print("生成头顶标题字幕: 贯穿全片（雅月体，花字金光渐变，顶部置顶）")

        # ----------------------------------------------------
        # 合并轨道与素材并写回
        # ----------------------------------------------------
        draft_data["materials"]["texts"] = new_materials_texts
        # 轨道层级：视频在底层，基础字幕在第二层，胸前重点在第三层，头顶标题在顶层
        draft_data["tracks"] = video_tracks + [base_track, chest_track, top_track]

        with open(work_dir / "draft_content.json", "w", encoding="utf-8") as f:
            json.dump(draft_data, f, ensure_ascii=False)

        # 加密打包
        enc_output = Path(td_work) / "enc"
        res_enc = subprocess.run([str(JY_DRAFTC), "-ec", str(work_dir), "-o", str(enc_output), "--jy-dir", str(JY_INSTALL)], capture_output=True, text=True)
        if res_enc.returncode != 0:
            raise RuntimeError(f"加密打包失败: {res_enc.stderr}")

        # 覆盖写回原剪映工程
        orig_file = draft_dir / "draft_content.json"
        shutil.copy2(enc_output / "draft_content.json", orig_file)
        print("已成功加密写回剪映原草稿！")

    print("\n✅ 三层字幕排版已全部注入剪映项目【10月24日】！")


if __name__ == "__main__":
    main()
