# 安装指南（ComfyUI 侧依赖）

本包自带脚本、工作流、提示词、案例图与 55 个精选姿势；ComfyUI 侧还需要
**3 个底模文件**。LoRA、VNCCS 节点和姿势库按你要用的路线选择安装，不必一次全下。

本指南按 Linux 环境编写（脚本使用 POSIX `fcntl` 文件锁）；Python 需 3.10 或更新版本。

## 0. 获取仓库并设置路径

如果还没有仓库副本：

```bash
git clone https://github.com/Arekejoker/qwen21-nsfw-pose-skill.git
cd qwen21-nsfw-pose-skill
```

在仓库根目录执行下面的设置。若 ComfyUI 不在 `~/ComfyUI`，把 `COMFY` 改成实际目录；
地址或输入/输出目录不同时，也可以调整对应环境变量。

```bash
export POSELAB="$PWD"
export COMFY="${COMFY:-$HOME/ComfyUI}"
export COMFYUI_URL="${COMFYUI_URL:-http://127.0.0.1:8188}"
export COMFYUI_INPUT="${COMFYUI_INPUT:-$COMFY/input}"
export COMFYUI_OUTPUT="${COMFYUI_OUTPUT:-$COMFY/output}"
export VNCCS_POSELIB="${VNCCS_POSELIB:-$COMFY/custom_nodes/ComfyUI_VNCCS_Utils/PoseLibrary}"

test -f "$POSELAB/SKILL.md" || { echo "请先 cd 到仓库根目录"; exit 1; }
test -f "$COMFY/main.py" || { echo "COMFY 路径不对：$COMFY（请设置为 ComfyUI 根目录）"; exit 1; }
mkdir -p "$COMFY/models/diffusion_models" "$COMFY/models/text_encoders" \
  "$COMFY/models/vae" "$COMFY/models/loras" "$COMFY/custom_nodes"
curl --fail --silent --show-error "$COMFYUI_URL/system_stats" >/dev/null \
  && echo "ComfyUI 已连接：$COMFYUI_URL"
```

这些 `export` 只对当前终端有效；新开终端时重新执行，或把它们保存到自己的 shell 配置文件。

### 按路线选择依赖

| 你要用的功能 | 必需依赖 |
| --- | --- |
| 路线① T2I | 3 个底模 + 默认 NSFW LoRA |
| 路线② Edit | 3 个底模；仅在需要脱衣编辑时再装 edit LoRA |
| 路线④ VNCCS 精确姿势 | 3 个底模 + VNCCS 节点/LoRA + 姿势库 + Playwright/CDP 浏览器 |
| 生成对比表 | 额外安装 `Pillow`：`python3 -m pip install Pillow` |

路线①②只用 Python 标准库，无需 `pip install`。路线④需要 Playwright Python 包：

```bash
python3 -m pip install playwright
```

路线④还需要可连接 CDP 的 `browser_client.py`；当前脚本会从
`~/.openclaw/tools/browser/browser_client.py` 导入它。该适配器不包含在仓库内，OpenClaw 主机之外
使用路线④时，需要自行提供等价适配器；路线①②不受影响。

## 1. 底模（3 文件，必需）

HF `Comfy-Org/Qwen-Image-2.1`（经 hf-mirror.com 直连，走代理会 SSL_ERROR）：

```bash
wget -c -P "$COMFY/models/diffusion_models" "https://hf-mirror.com/Comfy-Org/Qwen-Image-2.1/resolve/main/diffusion_models/qwen_image_2.1_int8_convrot.safetensors"
wget -c -P "$COMFY/models/text_encoders" "https://hf-mirror.com/Comfy-Org/Qwen-Image-2.1/resolve/main/text_encoders/qwen3vl_8b_int8_convrot.safetensors"
wget -c -P "$COMFY/models/vae" "https://hf-mirror.com/Comfy-Org/Qwen-Image-2.1/resolve/main/vae/qwen_image_2.1_vae_bf16.safetensors"
```

> 与 Civitai 作者同款底模（int8 convrot）。选它的原因：这些 LoRA 都是用它训/验证的。

## 2. LoRA（按路线选择，不需要全部安装）

| 文件 | 用于 | 下载 |
| --- | --- | --- |
| `qwen2_1-femaledVaginus-nsfw-v1_3-fine_L22-31.safetensors` (608M) | 路线①默认 | Civitai model `2986844`（tawsLoRa） |
| `qwen2_1-femaledVaginus-nsfw-v1.3-fine.safetensors` (608M) | 路线①备选 | 同上 |
| `thesealpacas-nsfw-v2.safetensors` (79.7M) | 路线①最露骨 | Civitai model `2958918` |
| `nsfw-posture-v3.safetensors` (84M) | 路线①姿势增强 | Civitai model `2988215` |
| `qwen21-nsfw-image-edit.safetensors` (84M) | 路线② | HF `RunningHubAI/Qwen-Image-2.1-NSFW-Image-Edit` |
| `VNCCS_QI2_PoseStudioV1.1.safetensors` (159M) | 路线④ | HF `MIUProject/VNCCS_PoseStudio_QI2.1` |

Civitai LoRA：打开对应模型页，选择表格里写明的版本和 `.safetensors` 文件，下载后放入
`$COMFY/models/loras/`。**文件名需与表格一致**，否则提示词配方和脚本中的 LoRA 名称无法匹配。

- tawsLoRa：<https://civitai.com/models/2986844>
- TheseAlpacas：<https://civitai.com/models/2958918>
- posture-v3：<https://civitai.com/models/2988215>

先装默认案例用的 `qwen2_1-femaledVaginus-nsfw-v1_3-fine_L22-31.safetensors` 即可；其余三个
Civitai LoRA 是可选配方。下载后可以检查文件是否在目录中：

```bash
ls -lh "$COMFY/models/loras"
```

HuggingFace：

```bash
wget -c -P "$COMFY/models/loras" "https://hf-mirror.com/RunningHubAI/Qwen-Image-2.1-NSFW-Image-Edit/resolve/main/qwen21-nsfw-image-edit.safetensors"
wget -c -P "$COMFY/models/loras" "https://hf-mirror.com/MIUProject/VNCCS_PoseStudio_QI2.1/resolve/main/LoRAs/VNCCS_QI2_PoseStudioV1.1.safetensors"
```

## 3. VNCCS_Utils 节点（路线④ 必需）

```bash
cd "$COMFY/custom_nodes"
git clone https://github.com/AHEKOT/ComfyUI_VNCCS_Utils.git
# 重启一次 ComfyUI 让节点加载
```

验证：`curl --fail --silent --show-error "$COMFYUI_URL/object_info" | grep -c VNCCS` 应 ≥ 1
（PoseStudio / PoseLibrary 节点都在）。

## 4. 姿势库（4 个仓库 + 本包 55 个精选，路线④）

```bash
for repo in \
  "Totemistyk/General_Poses_PoseStudio" \
  "Totemistyk/Ballet_PoseStudio" \
  "MIUProject/VNCCS_PoseLibrary_Main" \
  "MIUProject/MySuperPoseRepo"; do
  curl --fail-with-body --silent --show-error -X POST "$COMFYUI_URL/vnccs/pose_library/repositories/add" \
       -H "Content-Type: application/json" \
       --data "{\"repo_id\":\"$repo\"}"
done

# 刷新下载（首次会拉全部 JSON + webp 预览）
curl --fail-with-body --silent --show-error -X POST "$COMFYUI_URL/vnccs/pose_library/refresh"

# 本包 55 个精选姿势 → 拷入本地目录（仓库 refresh 不会删本地目录）
mkdir -p "$VNCCS_POSELIB/local_user_poses"
cp -a pose_library/local_user_poses/. "$VNCCS_POSELIB/local_user_poses/"

# 验证：应输出 136（81 仓库 + 55 本地）
curl --fail --silent --show-error "$COMFYUI_URL/vnccs/pose_library/list" | grep -c '"json_file"'
```

> **注意**：`refresh` 会删除远端清单里没有的本地文件。自定义/精选姿势务必放
> `PoseLibrary/local_user_poses/<分类>/`（永远列出、永不被自动清理）。

## 5. 运行脚本

```bash
# 路线①②
python3 scripts/qwen_pose_test.py --mode t2i --name test --prompt "..." \
  --lora "qwen2_1-femaledVaginus-nsfw-v1_3-fine_L22-31.safetensors" \
  --out outputs/test.png

# 路线④（需要一个 CDP 浏览器，默认连 127.0.0.1:18800）
python3 scripts/run_vnccs_ui.py --list-poses
python3 scripts/run_vnccs_ui.py --pose "squatting leaning back" \
  --char references/src_standing.png
```

环境变量（脚本内置默认值，按需覆盖）：
`COMFYUI_URL`、`COMFYUI_INPUT`、`COMFYUI_OUTPUT`、`POSELAB`（本包根）、
`QWEN_POSE_WORKFLOWS`（Qwen 工作流目录）、`VNCCS_WF_FILE`（VNCCS 工作流文件）、
`VNCCS_POSELIB`（VNCCS 节点自带 PoseLibrary 目录）、`VNCCS_UI_OUT`（输出目录）。

## 6. 安装自检清单

- [ ] `curl --fail --silent --show-error "$COMFYUI_URL/object_info" >/dev/null` 成功
- [ ] 按使用路线安装的 LoRA 出现在 `/object_info` 的 `LoraLoaderModelOnly` 选项里
- [ ] `VNCCS_PoseStudio` / `VNCCS_PoseLibrary` 节点在 `/object_info` 里
- [ ] 姿势库数量 = 136
- [ ] `python3 scripts/validate_package.py` 显示所有静态检查通过
- [ ] 跑一遍 README 快速开始，`outputs/author_case/shower.png` 生成且
      `*.png.json` 里 `ok: true`
