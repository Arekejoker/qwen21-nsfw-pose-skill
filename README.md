# qwen21-nsfw-pose

[![Package checks](https://github.com/Arekejoker/qwen21-nsfw-pose-skill/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/Arekejoker/qwen21-nsfw-pose-skill/actions/workflows/validate.yml)

**Qwen-Image 2.1 本地 NSFW / 姿势出图完整配方** — 作者级提示词结构 + NSFW LoRA + 136 个 3D 姿势库 + VNCCS 人偶精确姿势控制。

基于 ComfyUI + `qwen_image_2.1_int8_convrot` 底模（与 Civitai 作者同款底模），复刻并验证过 Civitai 作者样图（2026-10-12）。

- 适用：Claude Code / Codex / Cursor / OpenClaw（agent 技能）+ 人类手动使用
- 内容：可跟跑的作者案例、强制配方、姿势大胆度阶梯（L0–L3）、完整依赖与安装指南

**演示**（3D 人偶调姿势 → 一键生成 → 成品，Route ④）：

<img src="references/demo_pose_studio.gif" width="100%" alt="演示：3D 人偶变形 → 实时生成 → 成品" />

---

## 效果展示

### 本配方输出：同一海边场景的三级对照（L0 → L1 → L2）

| L0 · 全着装，无 LoRA（提示词即全部） | L1 · 湿身泳装 + LoRA@1.0 | L2 · 极低机位 + 湿身蹲姿 + LoRA@1.0 |
| --- | --- | --- |
| <img src="references/pose_examples/01_seaside.png" width="290" /> | <img src="references/pose_examples/01b_seaside_lora.png" width="290" /> | <img src="references/pose_examples/06_l2_squat_lowangle.png" width="290" /> |

三张图同场景递进：L0 只有提示词；L1 加 LoRA + 显式皮肤/水珠描写；L2 再加低机位与开合姿态。**LoRA 负责质感，提示词负责信息密度，机位负责大胆度。**

### NSFW 效果（⚠️ 以下图片包含裸露内容）

<details>
<summary><picture><img src="references/author_samples_cover_cursor.gif?v=3" width="100%" alt="作者原图（NSFW）· 点击卡片展开" /></picture><br/><b>👇 点击上方卡片展开作者原图（含裸露内容 · 18+，再点收起）</b></summary>

**作者原图**（Civitai showcase，本配方复刻的目标）：

| 作者 · 淋浴（tawsLoRa） | 作者 · 按摩（tawsLoRa） | 作者 · 自拍（TheseAlpacas） |
| --- | --- | --- |
| <img src="downloads/samples/taws_v13_shower_author.jpg" width="300" /> | <img src="downloads/samples/taws_v13_massage_author.jpg" width="300" /> | <img src="downloads/samples/thesealpacas_v2_selfie_author.jpg" width="300" /> |

</details>

用 §「快速开始」的命令可复刻淋浴那张（复刻输出已验证与作者原图同场景同构图，见 `downloads/samples/phase5_meta.json` 与本文快速开始一节）。

### 3D 人偶精确姿势（Route ④，136 姿势库）

默认人物图 `references/src_standing.png`；姿势 = 骨骼旋转 JSON（MakeHuman 网格 + three.js 渲染），
换姿势且保身份。姿势库来源：HuggingFace 4 个公开仓库（`Totemistyk/General_Poses`、
`Totemistyk/Ballet_PoseStudio`、`MIUProject/VNCCS_PoseLibrary_Main`、
`MIUProject/MySuperPoseRepo`）+ 55 个手工精选，共 **136 个**。

---

## 快速开始（作者案例跟跑）

前置安装见 [install/setup.md](install/setup.md)。装好后先跑一次自检（只读，不改动任何东西）：

```bash
python3 scripts/doctor.py
```

它逐项检查 ComfyUI 连通性、底模/LoRA、VNCCS 节点、姿势库、浏览器后端，并给出缺失项的修复指引。
全绿后一条命令复刻作者淋浴样图（~5 分钟）：

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

### 硬件要求（参考）

底模为 Qwen-Image 2.1 int8 套件，模型文件合计约 16GB（diffusion 6.8GB / text encoder 8.7GB / VAE 0.6GB），LoRA 各自 ≤608MB。

- **最低**：NVIDIA 12GB 显存 + 32GB 内存——能跑，ComfyUI 会自动把部分模型卸载到内存，出图慢一些
- **推荐**：24GB 显存（3090/4090 级）+ 32–64GB 内存——模型基本常驻，体验最顺
- **8GB 显存**：建议用 GGUF 量化版（社区实测 12–16GB 显存可跑 Q4；8GB 靠 offload 会明显更慢）
- 纯 CPU 不推荐（单张图耗时过长）
- 硬盘预留 ~40GB；CPU 无特殊要求（现代 x86_64/ARM 均可）；Linux 最省事，Windows 建议 WSL2，Mac 统一内存能跑但更慢
- 路线④额外需要一个可连接的桌面浏览器（Playwright/CDP，见 `install/setup.md`）

本仓库案例图与实测数据来自统一内存设备（DGX Spark）：1024×1024、40 步约 32 秒/张，峰值增量约 7–10GB。

## 三条路线

| 需求 | 路线 | 命令 |
| --- | --- | --- |
| 新 NSFW/性感图（文字出图） | ① T2I + NSFW LoRA（必开） | `scripts/qwen_pose_test.py --mode t2i` |
| 已有角色图换姿势（保脸/保服装） | ② Edit | `scripts/qwen_pose_test.py --mode edit` |
| 指定 3D 姿势库里的精确姿势 | ④ VNCCS PoseStudio | `scripts/run_vnccs_ui.py --pose <name> [--prompt "<场景>"]` |

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
├── scripts/            # doctor.py 自检、出图/自定义姿势脚本、浏览器 fallback、media_lock.py、validate_package.py
├── workflows/          # qwen21_t2i.json / qwen21_edit.json / VNCCS_PoseStudio_QI2.1.json
├── prompts/            # 3 篇作者原提示词 + 参数
├── references/         # 效果展示图（L0/L1/L2 海边对照）+ 默认人物图
├── downloads/samples/  # 作者原图 + 作者元数据 + 原始工作流 JSON
└── pose_library/       # 55 个手工精选姿势（安装时拷入 ComfyUI）
```

## 说明

- 本仓库原创代码与文档（`scripts/`、`workflows/`、`prompts/`、`SKILL.md`、README 等）采用 [Apache License 2.0](LICENSE)
- 第三方素材不在 Apache-2.0 覆盖范围内，权利归各自原作者：`downloads/samples/` 作者原图（Civitai 作者）、`pose_library/` 社区姿势与预览（MIUProject / Totemistyk，其中 Ballet 仓库为 MIT）、模型与 LoRA（HF `Comfy-Org/Qwen-Image-2.1`、Civitai 2986844 / 2958918 / 2988215、RunningHubAI、MIUProject 等）
- NSFW 示例图仅供配方演示；仓库为公开仓库，介意图片的先收藏后阅读
