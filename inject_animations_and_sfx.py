#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
剪映字幕动画与音效自动注入脚本 (JianYing Subtitle Animation & SFX Injector)
- 为字幕片段注入入场动画 (TextIntro)
- 为关键卡点注入对应搭配的音效 (SFX Audio Track)
- 动画与音效黄金搭配：
    * 滚入 ➔ 「收银叮」 (success-chime.mp3)
    * 折叠/展开 ➔ 「展开」 (modal-open.mp3)
    * 缩小 ➔ 「嘭」 (drop-thud.mp3)
    * 翻动 ➔ 「翻书」 (card-flip.mp3)
    * 滑动 ➔ 「WHOOSH」 (whoosh.mp3)
    * 吸入 ➔ 「水滴」 (sparkle.mp3)
    * 打字机 ➔ 「typing」 (type-fast.mp3)
    * 日出 ➔ 「叮」 (sparkle.mp3)
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

LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
DRAFT_ROOT = LOCALAPPDATA / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
JY_DRAFTC = Path(r"D:\project2026\软件开发\剪映字幕导出\bin\jy-draftc.exe")
JY_INSTALL = Path(r"C:\Users\Administrator\AppData\Local\JianyingPro\Apps\8.9.0.13361")
SFX_SOURCE_DIR = Path(r"C:\Users\Administrator\.agents\skills\huashu-design\assets\sfx")

# 音画动效搭配法则配置
MATCHING_RULES = [
    {
        "track_name": "头顶标题 (雅月体花字)",
        "seg_idx": 0,
        "anim": {"name": "日出", "id": "1644269", "resource_id": "6779084126457696776", "duration": 500000},
        "sfx": {"subpath": "magic/sparkle.mp3", "name": "日出·叮", "dur_us": 840000, "start_us": 100000}
    },
    {
        "track_name": "胸前重点 (经典黑)",
        "seg_idx": 0, # 【 正在开发新 Skill 】
        "anim": {"name": "复古打字机", "id": "17639720", "resource_id": "7253888335163167291", "duration": 800000},
        "sfx": {"subpath": "keyboard/type-fast.mp3", "name": "打字机·typing", "dur_us": 1520000, "start_us": 5400000}
    },
    {
        "track_name": "胸前重点 (经典黑)",
        "seg_idx": 1, # 【 自动校对 ➔ 写入剪映 】
        "anim": {"name": "向左滑动", "id": "1644277", "resource_id": "6763470195894784525", "duration": 500000},
        "sfx": {"subpath": "transition/whoosh.mp3", "name": "滑动·WHOOSH", "dur_us": 630000, "start_us": 15066000}
    },
    {
        "track_name": "胸前重点 (经典黑)",
        "seg_idx": 2, # 【 自动排版三层样式 】
        "anim": {"name": "折叠", "id": "3779439", "resource_id": "7125298122011447816", "duration": 500000},
        "sfx": {"subpath": "container/modal-open.mp3", "name": "折叠·展开", "dur_us": 630000, "start_us": 27533000}
    },
    {
        "track_name": "胸前重点 (经典黑)",
        "seg_idx": 3, # 【 动效合成 ➔ 秒发社媒 】
        "anim": {"name": "滚入", "id": "1644320", "resource_id": "7026674824537707038", "duration": 500000},
        "sfx": {"subpath": "feedback/success-chime.mp3", "name": "滚入·收银叮", "dur_us": 1040000, "start_us": 39666000}
    },
    {
        "track_name": "胸前重点 (经典黑)",
        "seg_idx": 4, # 【 基于 Gemini 3.8 Flash 】
        "anim": {"name": "缩小", "id": "1644263", "resource_id": "6724921217721045515", "duration": 500000},
        "sfx": {"subpath": "impact/drop-thud.mp3", "name": "缩小·嘭", "dur_us": 730000, "start_us": 62266000}
    }
]


def process_draft(draft_path: Path):
    print(f"\n>>> 正在为草稿 [{draft_path.name}] 注入字幕动画与音效...")

    # 1. 确保草稿媒体资源目录中复制好音效文件
    media_sfx_dir = draft_path / "Resources" / "sfx"
    media_sfx_dir.mkdir(parents=True, exist_ok=True)

    # 2. 解密草稿
    with tempfile.TemporaryDirectory() as td:
        plain_dir = Path(td) / "plain"
        subprocess.run([str(JY_DRAFTC), "-dc", str(draft_path), "-o", str(plain_dir), "--jy-dir", str(JY_INSTALL)], capture_output=True, check=True)
        with open(plain_dir / "draft_content.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        if "material_animations" not in data["materials"]:
            data["materials"]["material_animations"] = []
        if "audios" not in data["materials"]:
            data["materials"]["audios"] = []

        # 3. 注入动画与音效
        sfx_segments = []

        for rule in MATCHING_RULES:
            # 找到对应文本轨道的对应片段
            target_track = None
            for tr in data.get("tracks", []):
                if tr.get("name") == rule["track_name"]:
                    target_track = tr
                    break

            if not target_track or rule["seg_idx"] >= len(target_track.get("segments", [])):
                continue

            seg = target_track["segments"][rule["seg_idx"]]

            # 3.1 创建字幕入场动画
            anim_info = rule["anim"]
            anim_id = str(uuid.uuid4()).upper()
            anim_obj = {
                "animations": [
                    {
                        "anim_adjust_params": None,
                        "category_id": "",
                        "category_name": "",
                        "duration": anim_info["duration"],
                        "id": anim_info["id"],
                        "material_type": "sticker",
                        "name": anim_info["name"],
                        "panel": "",
                        "path": "",
                        "platform": "all",
                        "resource_id": anim_info["resource_id"],
                        "start": 0,
                        "type": "in"
                    }
                ],
                "id": anim_id,
                "multi_language_current": "none",
                "type": "sticker_animation"
            }
            data["materials"]["material_animations"].append(anim_obj)
            seg["extra_material_refs"] = [anim_id]
            print(f"  + 动画注入: [{rule['track_name']} 片段{rule['seg_idx']+1}] ➔ {anim_info['name']}")

            # 3.2 复制音效并添加到音频轨
            sfx_spec = rule["sfx"]
            src_sfx = SFX_SOURCE_DIR / sfx_spec["subpath"]
            dst_sfx = media_sfx_dir / src_sfx.name
            if src_sfx.exists():
                shutil.copy2(src_sfx, dst_sfx)

            audio_mat_id = str(uuid.uuid4()).upper()
            audio_mat_obj = {
                "aigc_history_id": "",
                "aigc_item_id": "",
                "app_id": 0,
                "category_id": "sfx",
                "category_name": "local",
                "check_flag": 1,
                "copyright_limit_type": "none",
                "duration": sfx_spec["dur_us"],
                "effect_id": "",
                "formula_id": "",
                "id": audio_mat_id,
                "intensifies_path": "",
                "is_ai_clone_tone": False,
                "is_text_edit_overdub": False,
                "is_ugc": False,
                "local_material_id": audio_mat_id,
                "music_id": audio_mat_id,
                "name": sfx_spec["name"],
                "path": str(dst_sfx).replace("\\", "/"),
                "query": "",
                "request_id": "",
                "resource_id": "",
                "search_id": "",
                "source_from": "",
                "source_platform": 0,
                "team_id": "",
                "text_id": "",
                "tone_category_id": "",
                "tone_category_name": "",
                "tone_effect_id": "",
                "tone_effect_name": "",
                "tone_platform": "",
                "tone_second_category_id": "",
                "tone_second_category_name": "",
                "tone_speaker": "",
                "tone_type": "",
                "type": "sound_effect",
                "video_id": "",
                "wave_points": []
            }
            data["materials"]["audios"].append(audio_mat_obj)

            audio_seg_id = str(uuid.uuid4()).upper()
            audio_seg_obj = {
                "caption_info": None,
                "cartoon": False,
                "clip": None,
                "common_keyframes": [],
                "enable_adjust": True,
                "enable_color_correct_adjust": False,
                "enable_color_curves": False,
                "enable_color_match_adjust": False,
                "enable_color_wheels": False,
                "enable_lut": False,
                "enable_smart_color_adjust": False,
                "extra_material_refs": [],
                "group_id": "",
                "hdr_settings": None,
                "id": audio_seg_id,
                "intensifies_audio": False,
                "is_placeholder": False,
                "is_tone_modify": False,
                "keyframe_refs": [],
                "last_nonzero_volume": 1.0,
                "material_id": audio_mat_id,
                "render_index": 0,
                "responsive_layout": False,
                "reverse": False,
                "source_timerange": {"duration": sfx_spec["dur_us"], "start": 0},
                "speed": 1.0,
                "target_timerange": {"duration": sfx_spec["dur_us"], "start": sfx_spec["start_us"]},
                "template_id": "",
                "template_scene": "default",
                "track_attribute": 0,
                "track_render_index": 0,
                "uniform_scale": {"on": True, "value": 1.0},
                "visible": True,
                "volume": 0.8
            }
            sfx_segments.append(audio_seg_obj)
            print(f"  + 音效卡点: [{sfx_spec['name']}] ➔ 起始时间 {sfx_spec['start_us']//1000}ms, 音量 0.8")

        # 4. 组装音效轨道
        if sfx_segments:
            sfx_track = {
                "attribute": 0,
                "flag": 0,
                "id": str(uuid.uuid4()).upper(),
                "is_default_name": False,
                "name": "字幕音效 (自动搭配)",
                "segments": sfx_segments,
                "type": "audio"
            }
            # 移除旧的同名音效轨（如有）
            data["tracks"] = [tr for tr in data["tracks"] if tr.get("name") != "字幕音效 (自动搭配)"]
            data["tracks"].append(sfx_track)

        # 5. 保存明文并重新加密
        with tempfile.TemporaryDirectory() as td_enc:
            plain_out = Path(td_enc) / "plain"
            plain_out.mkdir()
            with open(plain_out / "draft_content.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

            enc_out = Path(td_enc) / "enc"
            subprocess.run([str(JY_DRAFTC), "-ec", str(plain_out), "-o", str(enc_out), "--jy-dir", str(JY_INSTALL)], capture_output=True, check=True)

            # 覆盖原工程的 draft_content.json
            shutil.copy2(enc_out / "draft_content.json", draft_path / "draft_content.json")

    print(f"✅ 草稿 [{draft_path.name}] 动画与音效已成功加密注入！")


def main():
    print("=== 开始为剪映工程注入字幕动画与音效卡点 ===")
    draft1 = DRAFT_ROOT / "10月25日 (AI精修字幕)"
    draft2 = DRAFT_ROOT / "10月25日"

    if draft1.exists():
        process_draft(draft1)
    if draft2.exists():
        process_draft(draft2)

    print("\n🎉 全部处理完成！请在剪映中退出项目并重新打开查看效果！")


if __name__ == "__main__":
    main()
