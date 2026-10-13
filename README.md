# qwen21-nsfw-pose

[![Package checks](https://github.com/Arekejoker/qwen21-nsfw-pose-skill/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/Arekejoker/qwen21-nsfw-pose-skill/actions/workflows/validate.yml)

**Qwen-Image 2.1 本地 NSFW / 姿势出图完整配方** — 作者级提示词结构 + NSFW LoRA + 136 个 3D 姿势库 + VNCCS 人偶精确姿势控制。

基于 ComfyUI + `qwen_image_2.1_int8_convrot` 底模（与 Civitai 作者同款底模），复刻并验证过 Civitai 作者样图（2026-10-12）。

- 适用：Claude Code / Codex / Cursor / OpenClaw（agent 技能）+ 人类手动使用
- 内容：可跟跑的作者案例、强制配方、姿势大胆度阶梯（L0–L3）、完整依赖与安装指南

---

## 效果展示

### 本配方输出：同一海边场景的三级对照（L0 → L1 → L2）

| L0 · 全着装，无 LoRA（提示词即全部） | L1 · 湿身泳装 + LoRA@1.0 | L2 · 极低机位 + 湿身蹲姿 + LoRA@1.0 |
| --- | --- | --- |
| <img src="references/pose_examples/01_seaside.png" width="290" /> | <img src="references/pose_examples/01b_seaside_lora.png" width="290" /> | <img src="references/pose_examples/06_l2_squat_lowangle.png" width="290" /> |

三张图同场景递进：L0 只有提示词；L1 加 LoRA + 显式皮肤/水珠描写；L2 再加低机位与开合姿态。**LoRA 负责质感，提示词负责信息密度，机位负责大胆度。**

### NSFW 效果（⚠️ 以下图片包含裸露内容）

**作者原图**（Civitai showcase，本配方复刻的目标）：

| 作者 · 淋浴（tawsLoRa） | 作者 · 按摩（tawsLoRa） | 作者 · 自拍（TheseAlpacas） |
| --- | --- | --- |
| <img src="downloads/samples/taws_v13_shower_author.jpg" width="300" /> | <img src="downloads/samples/taws_v13_massage_author.jpg" width="300" /> | <img src="downloads/samples/thesealpacas_v2_selfie_author.jpg" width="300" /> |

用 §「快速开始」的命令可复刻淋浴那张（复刻输出已验证与作者原图同场景同构图，见 `downloads/samples/phase5_meta.json` 与本文快速开始一节）。

### 3D 人偶精确姿势（Route ④，136 姿势库）

默认人物图 `references/src_standing.png`；姿势 = 骨骼旋转 JSON（MakeHuman 网格 + three.js 渲染），
换姿势且保身份。姿势库来源：HuggingFace 4 个公开仓库（`Totemistyk/General_Poses`、
`Totemistyk/Ballet_PoseStudio`、`MIUProject/VNCCS_PoseLibrary_Main`、
`MIUProject/MySuperPoseRepo`）+ 55 个手工精选，共 **136 个**。

---

## 快速开始（作者案例跟跑）

前置安装见 [install/setup.md](install/setup.md)。装好后一条命令复刻作者淋浴样图（~5 分钟）：

```bash
python3 scripts/qwen_pose_test.py \
  --mode t2i --name author_case_shower \
  --prompt "$(cat prompts/taws_v13_shower.txt)" \
  --seed 80964 \
  --steps 50 --cfg 2.5 --sampler er_sde --scheduler beta \
  --width 1152 --height 1728 \
  --lora "qwen2_1-femaledVaginus-nsfw-v1_3-fine_L22-31.safetensors" \
  --lora-strength 1.0 \
  --out outputs/author_case/shower.png
```

对比对象：`downloads/samples/taws_v13_shower_author.jpg`。
完整元数据（提示词/参数/seed/完整工作流）：`downloads/samples/phase5_meta.json`。

## 三条路线

| 需求 | 路线 | 命令 |
| --- | --- | --- |
| 新 NSFW/性感图（文字出图） | ① T2I + NSFW LoRA（必开） | `scripts/qwen_pose_test.py --mode t2i` |
| 已有角色图换姿势（保脸/保服装） | ② Edit | `scripts/qwen_pose_test.py --mode edit` |
| 指定 3D 姿势库里的精确姿势 | ④ VNCCS PoseStudio | `scripts/run_vnccs_ui.py --pose <name>` |

姿势怎么选（大胆度阶梯 L0–L3、用户要求→姿势族映射表）：见 `SKILL.md` §4，或
`scripts/run_vnccs_ui.py --list-poses` 列出全部 136 个姿势。

## 配方要点（摘要）

- `er_sde` + `beta`，CFG 2.5，50 步，1152×1728 竖版
- **NSFW LoRA 永远开**（默认 `femaledVaginus v1.3b` @ 1.0）
- 提示词必须按作者结构写满 7 要素、300–1500 字符、含 LoRA 触发词
- 弱化配方（无 LoRA/短提示词/减步数）前必须告知用户代价，不许默默减弱

完整规则与证据：`SKILL.md`。

## 目录结构

```
├── SKILL.md            # agent 技能（完整规则）
├── install/setup.md    # 安装指南（模型/LoRA/节点/姿势库）
├── scripts/            # 出图脚本、案例脚本、media_lock.py、validate_package.py
├── workflows/          # qwen21_t2i.json / qwen21_edit.json / VNCCS_PoseStudio_QI2.1.json
├── prompts/            # 3 篇作者原提示词 + 参数
├── references/         # 效果展示图（L0/L1/L2 海边对照）+ 默认人物图
├── downloads/samples/  # 作者原图 + 作者元数据 + 原始工作流 JSON
└── pose_library/       # 55 个手工精选姿势（安装时拷入 ComfyUI）
```

## 说明

- 底模与 LoRA 版权归原作者所有（HF `Comfy-Org/Qwen-Image-2.1`、Civitai 2986844 / 2958918 / 2988215）
- NSFW 示例图仅供配方演示；仓库为公开仓库，介意图片的先收藏后阅读
