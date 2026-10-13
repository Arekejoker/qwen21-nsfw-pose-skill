# 安装指南（ComfyUI 侧依赖）

本包自带脚本、工作流、提示词、案例图与 55 个精选姿势；ComfyUI 侧还需要
**3 个底模文件 + 6 个 LoRA + 1 个节点 + 4 个姿势仓库**。

默认假设 ComfyUI 在 `http://127.0.0.1:8188`（`COMFYUI_URL` 可改），模型目录在
`~/ComfyUI/models`（按你的实际 ComfyUI 路径调整；下文 `$COMFY` 代指 ComfyUI 根目录）。

## 1. 底模（3 文件，必需）

HF `Comfy-Org/Qwen-Image-2.1`（经 hf-mirror.com 直连，走代理会 SSL_ERROR）：

```bash
cd $COMFY/models
# 下载目录按你 ComfyUI 的模型扫描配置，通常是：
#   diffusion_models/  text_encoders/  vae/

wget -P diffusion_models/ "https://hf-mirror.com/Comfy-Org/Qwen-Image-2.1/resolve/main/diffusion_models/qwen_image_2.1_int8_convrot.safetensors"
wget -P text_encoders/    "https://hf-mirror.com/Comfy-Org/Qwen-Image-2.1/resolve/main/text_encoders/qwen3vl_8b_int8_convrot.safetensors"
wget -P vae/              "https://hf-mirror.com/Comfy-Org/Qwen-Image-2.1/resolve/main/vae/qwen_image_2.1_vae_bf16.safetensors"
```

> 与 Civitai 作者同款底模（int8 convrot）。选它的原因：这些 LoRA 都是用它训/验证的。

## 2. LoRA（6 文件，按路线取）

| 文件 | 用于 | 下载 |
| --- | --- | --- |
| `qwen2_1-femaledVaginus-nsfw-v1_3-fine_L22-31.safetensors` (608M) | 路线①默认 | Civitai model `2986844`（tawsLoRa） |
| `qwen2_1-femaledVaginus-nsfw-v1.3-fine.safetensors` (608M) | 路线①备选 | 同上 |
| `thesealpacas-nsfw-v2.safetensors` (79.7M) | 路线①最露骨 | Civitai model `2958918` |
| `nsfw-posture-v3.safetensors` (84M) | 路线①姿势增强 | Civitai model `2988215` |
| `qwen21-nsfw-image-edit.safetensors` (84M) | 路线② | HF `RunningHubAI/Qwen-Image-2.1-NSFW-Image-Edit` |
| `VNCCS_QI2_PoseStudioV1.1.safetensors` (159M) | 路线④ | HF `MIUProject/VNCCS_PoseStudio_QI2.1` |

Civitai 下载（需 token；`~/.config/civitai/config.yaml` 里的 `api_token`）：

```bash
pip install civitai
# 大文件直连下载（官方 CLI 偶发超时，curl 更稳）：
curl -H "Authorization: Bearer $CIVITAI_TOKEN" -O <model_file_url>
# model_file_url 可用 civitai CLI 或网页拿；三个模型的 v1.3b / v2 / posture-v3
# 文件名见上表
```

HuggingFace：

```bash
wget -P $COMFY/models/loras/ "https://hf-mirror.com/RunningHubAI/Qwen-Image-2.1-NSFW-Image-Edit/resolve/main/qwen21-nsfw-image-edit.safetensors"
wget -P $COMFY/models/loras/ "https://hf-mirror.com/MIUProject/VNCCS_PoseStudio_QI2.1/resolve/main/LoRAs/VNCCS_QI2_PoseStudioV1.1.safetensors"
```

## 3. VNCCS_Utils 节点（路线④ 必需）

```bash
cd $COMFY/custom_nodes
git clone https://github.com/AHEKOT/ComfyUI_VNCCS_Utils
# 重启一次 ComfyUI 让节点加载
```

验证：`curl -s 127.0.0.1:8188/object_info | grep -c VNCCS` 应 ≥ 1（PoseStudio /
PoseLibrary 节点都在）。

## 4. 姿势库（4 个仓库 + 本包 55 个精选，路线④）

```bash
for repo in \
  "Totemistyk/General_Poses_PoseStudio" \
  "Totemistyk/Ballet_PoseStudio" \
  "MIUProject/VNCCS_PoseLibrary_Main" \
  "MIUProject/MySuperPoseRepo"; do
  curl -s -X POST 127.0.0.1:8188/vnccs/pose_library/repositories/add \
       -d "{\"repo_id\":\"$repo\"}"
done

# 刷新下载（首次会拉全部 JSON + webp 预览）
curl -s -X POST 127.0.0.1:8188/vnccs/pose_library/refresh

# 本包 55 个精选姿势 → 拷入本地目录（仓库 refresh 不会删本地目录）
cp -r pose_library/local_user_poses $COMFY/custom_nodes/ComfyUI_VNCCS_Utils/PoseLibrary/

# 验证：应输出 136（81 仓库 + 55 本地）
curl -s 127.0.0.1:8188/vnccs/pose_library/list | grep -c '"json_file"'
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
`COMFYUI_URL`、`COMFYUI_INPUT`、`COMFYUI_OUTPUT`、`POSLAB`（本包根）、
`VNCCS_POSELIB`（VNCCS 节点自带 PoseLibrary 目录）、`VNCCS_UI_OUT`（输出目录）。

## 6. 安装自检清单

- [ ] `curl -s 127.0.0.1:8188/object_info | grep -o qwen_image_2.1_int8_convrot.safetensors | head -1` 有输出
- [ ] 6 个 LoRA 全部出现在 `/object_info` 的 `LoraLoaderModelOnly` 选项里
- [ ] `VNCCS_PoseStudio` / `VNCCS_PoseLibrary` 节点在 `/object_info` 里
- [ ] 姿势库数量 = 136
- [ ] 跑一遍 README 快速开始，`outputs/author_case/shower.png` 生成且
      `*.png.json` 里 `ok: true`
