---
name: qwen21-nsfw-pose
description: Use when generating sexy/NSFW or posed images with local Qwen-Image 2.1 — pose/NSFW LoRAs (tawsLoRa femaledVaginus, TheseAlpacas, posture-v3), pose transfer from an existing image, or exact pose control via VNCCS PoseStudio 3D pose library. Triggers: 性感姿势, 摆姿势, NSFW 出图, 换姿势, 姿势控制, pose transfer, pose lora, VNCCS, 人偶姿势, 姿势库. Independent of any general image-generation skill (which handles SFW text/edit/cutout work).
license: Apache-2.0
---

# Qwen-Image 2.1 NSFW / Pose Pipeline

Local photorealistic NSFW + pose control: ComfyUI + Qwen-Image 2.1 (int8 convrot)
+ NSFW LoRAs + a 136-pose VNCCS 3D pose library.

**Path convention:** everything in this skill is relative to the skill root
(this directory). Scripts in `scripts/`, workflow graphs in `workflows/`,
author prompts in `prompts/`, reference images in `references/`,
author sample data (originals + metadata) in `downloads/samples/`.
ComfyUI-side locations (models, LoRAs, pose library) are configurable via env
vars — see `install/setup.md` and §2. The default host for ComfyUI is
`http://127.0.0.1:8188` (override with `COMFYUI_URL`).

This file is self-contained: setup, recipe, pose selection, and a first-run
author case are all inside.

## 0. First run — follow the author's case (recommended)

The fastest way to trust the pipeline is re-running the author's own sample
prompt and comparing against the author's published image (verified 2026-10-12):

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

- Other cases: `prompts/taws_v13_massage.txt` (30 steps, same seed, per its
  `.params.json`) and `prompts/thesealpacas_v2_selfie.txt` (CFG 4.0 +
  `thesealpacas-nsfw-v2` @0.8; its `.txt` ends with a `[negative]` section —
  pass that to `--negative`).
- Author originals to compare against: `downloads/samples/*_author.jpg`
  (shower / massage / selfie). Full author metadata (prompts/params/seed/
  complete ComfyUI graph) in `downloads/samples/phase5_meta.json`.

## 1. Routing

| Request | Route | Tool |
| --- | --- | --- |
| New sexy/NSFW image from a text idea | ① T2I + NSFW LoRA (mandatory) | `scripts/qwen_pose_test.py --mode t2i` |
| Change pose of an existing character image (keep face/clothes) | ② Edit | `scripts/qwen_pose_test.py --mode edit` |
| Change pose from a 3D mannequin render (script, no browser) | ③ Pose transfer | `scripts/run_pose_transfer.py` |
| Exact pose from the 3D pose library (136 poses) | ④ VNCCS PoseStudio | `scripts/run_vnccs_ui.py` (browser automation) |
| Do NOT use: a plain photo or illustration as pose reference — the model composites it as a second person, or redraws the reference person entirely (tested twice); use a textureless 3D mannequin render with route ③/④ instead | | |

Outputs land under `./outputs/` (the scripts create directories as needed).

## 2. Setup — what this package contains and what to install

### 2.1 In this package

| Path | Content |
| --- | --- |
| `SKILL.md` | this file |
| `scripts/` | `doctor.py` (read-only environment self-check: ComfyUI, models, LoRAs, VNCCS, pose library, browser stack — every check degrades to WARN/SKIP with a fix hint), `qwen_pose_test.py` (routes ①②), `run_pose_transfer.py` (route ③: pose transfer from a 3D mannequin render, no browser), `run_vnccs_ui.py` (route ④), `make_custom_pose.py` (new pose from a library pose by bone rotation), `run_phase5.py` + `build_phase5_sheet.py` (case re-run & comparison sheet), `media_lock.py` (shared media lock, bundled), `browser_fallback.py` (standalone CDP fallback when the OpenClaw adapter is absent), `validate_package.py` (offline package integrity check) |
| `workflows/` | `qwen21_t2i.json`, `qwen21_edit.json` (official Qwen-Image 2.1 graphs), `VNCCS_PoseStudio_QI2.1.json` |
| `prompts/` | the 3 author prompts + `.params.json` (the exact local-test settings) |
| `references/` | `pose_examples/` (L0/L1/L2 seaside examples), `src_standing.png` (default character for route ④) |
| `downloads/samples/` | author originals `*_author.jpg` (shower/massage/selfie) + `phase5_meta.json` (prompt, params, seed, complete graph JSONs) + the 3 raw ComfyUI graph files — used by `scripts/run_phase5.py` & `build_phase5_sheet.py` |
| `pose_library/local_user_poses/Uncategorized/` | 55 curated extra pose JSONs + previews — copy into ComfyUI's `PoseLibrary/local_user_poses/Uncategorized/` after installing the node |
| `install/setup.md` | full install guide (models, LoRAs, node, pose repos, commands) |

### 2.2 ComfyUI-side dependencies (see `install/setup.md` for exact commands)

- **Base models (3 files)** from HF `Comfy-Org/Qwen-Image-2.1`:
  `diffusion_models/qwen_image_2.1_int8_convrot.safetensors`,
  `text_encoders/qwen3vl_8b_int8_convrot.safetensors`,
  `vae/qwen_image_2.1_vae_bf16.safetensors` — into the ComfyUI model dirs.
- **LoRAs** (into ComfyUI `models/loras/`):

| File (size) | Use | Source |
| --- | --- | --- |
| `qwen2_1-femaledVaginus-nsfw-v1_3-fine_L22-31.safetensors` (608M) | default: anatomy + pose, sharpest | Civitai model 2986844 — tawsLoRa "Qwen Image 2.1 - FemaledVaginus-NSFW" |
| `qwen2_1-femaledVaginus-nsfw-v1.3-fine.safetensors` (608M) | same family, v1.3 | Civitai model 2986844 |
| `thesealpacas-nsfw-v2.safetensors` (79.7M) | most reveal, "influencer" face drift | Civitai model 2958918 |
| `nsfw-posture-v3.safetensors` (84M) | strongest pose/body emphasis | Civitai model 2988215 |
| `qwen21-nsfw-image-edit.safetensors` (84M) | edit-route undress/pose changes | HF `RunningHubAI/Qwen-Image-2.1-NSFW-Image-Edit` (mirror of oreolove "Nude Edit"; original Civitai page delisted) |
| `VNCCS_QI2_PoseStudioV1.1.safetensors` (159M) | only for route ④ | HF `MIUProject/VNCCS_PoseStudio_QI2.1` (same repo as the workflow JSON) |

- **VNCCS_Utils custom node**: https://github.com/AHEKOT/ComfyUI_VNCCS_Utils →
  clone into `ComfyUI/custom_nodes/`, then restart ComfyUI once.
- **Pose library**: 4 HuggingFace repos (the public catalog as of 2026-10-12):
  `Totemistyk/General_Poses_PoseStudio` (50), `Totemistyk/Ballet_PoseStudio`
  (3 in manifest; the repo actually ships 58 — register + refresh, then copy
  this package's 55 curated extras into `local_user_poses/Uncategorized/`),
  `MIUProject/VNCCS_PoseLibrary_Main` (16), `MIUProject/MySuperPoseRepo` (12).
  Register: `curl -X POST 127.0.0.1:8188/vnccs/pose_library/repositories/add
  -d '{"repo_id":"<owner>/<repo>"}'`. Total after setup: 136.
  **A repo refresh deletes local files not in the remote manifest** — extra/
  curated poses belong in `PoseLibrary/local_user_poses/<Category>/`
  (always listed, never auto-cleaned). Pose list API: `GET /vnccs/pose_library/list`.
- **Route ④ extras**: any CDP Chrome (default `127.0.0.1:18800`) +
  `browser_client.py` + playwright. On the original host these live in
  `~/.openclaw/tools/browser/`; elsewhere point `run_vnccs_ui.py` at an
  equivalent CDP endpoint (it only needs `connect_sync(playwright)` to return a
  browser with one context — a minimal stand-in is fine).
- **media_lock**: bundled in `scripts/`; both scripts import it first from the
  package, then fall back to `~/.openclaw/tools`.

The base model is `qwen_image_2.1_int8_convrot.safetensors` — the same model
the Civitai authors of these LoRAs used, so their published prompts/params
transfer well. (Note: one of the three author samples actually ran on a
different base with 5 stacked LoRAs; we reproduced it with the single
thesealpacas-v2 LoRA on the convrot base — see Parameter provenance below.)

Download tips (verified): Civitai via the official CLI or
`curl -H "Authorization: Bearer <token>" <file-url>`; HuggingFace via
`hf-mirror.com` directly (no proxy — a proxy causes SSL_ERROR).

## 3. Route ① — T2I (the "author recipe", validated 2026-10-12)

### 3.1 Mandatory recipe — do not weaken silently

This recipe reproduces Civitai showcase-level results. **All of the following are
part of the recipe; a deviation changes the result and must be told to the user:**

- **Sampler** `er_sde` + scheduler `beta` (not euler/simple)
- **CFG 2.5** (the A1 reference; 2.5–4 works, CFG 1 starves the LoRA)
- **Steps = the reference sample's value: 50** (A1 provenance, table below)
- **Size 1152×1728 portrait 2:3** (`--width 1152 --height 1728`); keep
  `--resolution 1024` (that flag feeds `TextEncodeQwenImage21`, it is not pixel size)
- **A LoRA is always on for route ①.** Default:
  `qwen2_1-femaledVaginus-nsfw-v1_3-fine_L22-31.safetensors` @ **1.0**
- **The prompt is the main lever** — it must follow the author structure
  (§3.2) at the author's density (300–1500 characters, explicit terms).
  Short/keyword prompts and SFW-generic phrasing are what make output look bland.
- **Pass the reference sample's seed** when you claim "reproduction"
  (A1 seed = 80964). The harness default seed (424242) is fine for new
  creative runs but must not be labelled as the author's result.

Parameter provenance (source: `scripts/run_phase5.py` + each run's `*.png.json`):

| Run record | Steps | CFG | Seed | LoRA strength (local test) |
| --- | --- | --- | --- | --- |
| A1 shower (primary reference) | 50 | 2.5 | 80964 | 1.0 |
| A2 massage (separate sample) | 30 | 2.5 | 80964 | 1.0 |
| B1 selfie | 50 | 4.0 | 124880844757561 | 0.8 (thesealpacas-v2) |
| C1 control | 50 | 2.5 | 80964 | no LoRA |

Preserve each sample's settings as a unit; do not mix one sample's prompt with
another sample's params and present it as "the author recipe".

### 3.2 Prompt structure (copy the pattern, fill the scene)

The working prompts all contain, in this order — write all 7, no omissions:
1. Camera: "A hyper-realistic photograph / low-angle shot / top-down overhead shot", lens and angle
2. Subject: age, build, hair (color, wet/dry, placement)
3. Pose: pick one from the pose ladder (§4) and spell out each limb (which leg bent, where the hands are, what the head/gaze does)
4. Setting + lighting: "warm steamy light", "neon bokeh", "soft morning light through sheer curtains"
5. Skin: "glistening", "visible pores", "natural skin texture", "slick oily sheen"
6. Anatomy/reveal where desired — the LoRAs were trained on explicit terms
   (e.g. "labia majora ... innie distinctly visible"); generic words ("seductive")
   do almost nothing
7. Finish: "8k resolution, cinematic lighting, candid 'caught in the moment'
   atmosphere, photorealistic anatomy"

Template (a real author prompt runs 300–1500 chars):

```
A hyper-realistic, {camera} shot {subject with age/build/hair state},
{one pose from §4, limb by limb}. {Setting + lighting}. Her skin is
{glistening/visible pores/slick oily sheen}. {explicit anatomy/reveal wording}.
{face/expression}. 8k resolution, cinematic lighting, candid "caught in the
moment" atmosphere, photorealistic anatomy.
```

**Before writing, load a verified author prompt and rewrite it for your scene** —
`prompts/*.txt` (+ matching `.params.json`). Writing from scratch is what makes
results look generic.

### 3.3 Deviations — tell, don't silently do it

If the user asks for a shorter prompt, a SFW-generic prompt, "no LoRA", fewer
steps, or a different sampler — **and** if you (the agent) ever need to deviate
from the recipe for any reason (model refuses a token, out-of-memory, etc.):
say the expected cost out loud, show the evidence, and proceed only after
confirmation. Never present a weakened run as "the recipe's result"; label what
was changed next to the delivered image. Evidence to cite:

- **True controlled experiment (single variable = LoRA):** `C1` (author prompt,
  50 steps, seed 80964, **no LoRA**) vs `A1` (identical prompt/params + LoRA):
  no-LoRA still looks showcase-grade as a photograph, but the LoRA is what adds
  the skin/gloss/anatomy detail the author's images have. So "no LoRA" ≈
  "good photograph, not the author's texture".
- **Visual demo (multiple variables: prompt + outfit + LoRA + seed):**
  `references/pose_examples/01_seaside.png` (L0, no LoRA) vs
  `01b_seaside_lora.png` (L1 + LoRA) vs `06_l2_squat_lowangle.png`
  (L2 + low angle + LoRA) — shows the ladder of how much the full recipe adds.
  It demonstrates the effect but does **not** isolate any single factor.

### 3.4 Known limits of the harness

- **One LoRA per run.** `qwen_pose_test.py` injects a single `LoraLoaderModelOnly`
  (node id 99) between `UNETLoader` and `KSampler`. Civitai showcase workflows
  often stack 3–5 LoRAs; to reproduce those, chain extra `LoraLoaderModelOnly`
  nodes in `build_workflow()`.
- **No refine pass / no EasyCache.** Authors add a 2× lanczos upscale + a 25-step
  `denoise 0.35` pass and `EasyCache`; `QwenImage21Cache` is broken on the
  original host (`aimdo memory compile error`) and the route ④ runner removes it.
  A/B runs matched the authors' look without the refine pass — add it only when
  a job needs extra sharpness.

## 4. Pose selection (the "boldness scale") — match the user's request

Read the user's request (clothes state, desired mood, scene) → pick a tier →
give a **concrete pose**, not a vague one. "Bold" is three levers combined:
**pose openness × camera angle × clothing/wet state**.

### 4.1 Tiers (English wording to use in route ① prompts)

- **L0 closed / editorial** (clothed SFW): standing with weight on one leg, hand
  on hip or in pocket; sitting on a chair, legs crossed at the ankles; leaning on
  a railing/wall, looking back over the shoulder; mid-stride walking.
- **L1 open** (swimwear / wet / relaxed): crouching with knees apart, hands on
  the floor; sitting on the floor with knees opened to one side; lying on her
  side in bed, propped on an elbow, looking back over the shoulder; kneeling with
  hands behind; reclining on a sofa with legs open.
- **L2 bold** (author style — always pair with the NSFW LoRA + low angle):
  standing with legs apart, shot from a low angle looking up; lying prone with
  hips lifted toward the camera; sitting with legs wide open, leaning forward on
  the elbows; kneeling on one knee with the other leg extended to the side, torso
  arched back; lying on her back with legs open, one hand behind the head.
- **L3 extreme / cropped**: extreme low angle looking up between open legs;
  overhead shot lying flat with legs open; cropped framing (waist-up or
  mid-thigh) to emphasize the pose.

### 4.2 Suggestion table (user request → tier → concrete pose)

| User asks for (examples) | Tier | Route ④ library pose families (`--list-poses` names) | Route ① prompt wording |
| --- | --- | --- | --- |
| 全着装、自然/编辑感 (standing, portrait, office/street) | L0 | Standing / Sitting / Walking / Close Up | standing with weight on one leg, hand in pocket; seated on a chair, legs crossed at the ankles |
| 泳装/湿身/海滩/浴室 (swimwear, wet, relaxed) | L1 | Squatting / Kneeling / Laying Back | crouching with knees apart, hands on the floor, looking back over the shoulder |
| 大胆/NSFW (nude + LoRA, low angle, "author style") | L2 | Kneeling / Laying Back / Prone / Splits / Crawling / Dancing on knees | standing with legs apart from a low angle; prone with hips lifted toward the camera; seated wide, leaning forward on elbows |
| 极端/特写构图 (crop, extreme low, overhead) | L3 | Splits / any L2 family + crop framing | extreme low angle looking up between open legs; overhead, lying flat with legs open |

Rules:
1. Decide the reveal first: clothed → L0; swimwear/wet → L1; nude + NSFW LoRA → L2.
   **Pairing the LoRA with an L0 pose is the most common cause of "bland" NSFW
   output** (observed, not a proven law).
2. Camera angle amplifies the pose (empirical heuristic): low angle ≈ +1
   boldness, overhead ≈ +1. "Low angle + L1" ≈ "eye level + L2" — this is why
   the author's shower/massage shots read as bold despite simple poses.
3. One pose per prompt, limb by limb; two competing pose descriptions get blended.
4. When the user names a pose they saw somewhere, search the library first:
   `python3 scripts/run_vnccs_ui.py --list-poses` (136 entries with file paths).

## 5. Route ② — Edit (pose change with identity preservation)

```bash
python3 scripts/qwen_pose_test.py \
  --mode edit --name pose_change --input /absolute/base.png \
  --prompt "change her pose to kneeling on one knee, hands on hips, keep face hair and outfit" \
  --cfg 3 --sampler er_sde --scheduler beta --steps 20 \
  --out outputs/pose_change.png
```

CFG 3 is more stable for edit mode. SFW instruction prompts keep NSFW LoRAs from
triggering; add `--lora qwen21-nsfw-image-edit.safetensors` only when undressing.

## 6. Route ③ — Scripted pose transfer (3D mannequin reference)

```bash
python3 scripts/run_pose_transfer.py \
  --char /absolute/character.png \
  --pose-ref /absolute/doll_render.png \
  --out outputs/pose_transfer.png [--seed N] [--steps 25]
```

The pose source must be a textureless **3D mannequin render** — e.g. the
`doll_*.png` captures that route ④ saves under the ComfyUI output dir, or any
3D poser render of the target pose. Photos and illustrations as pose references
do NOT work: the model composites the reference person as a second person, or
redraws the reference person entirely (retested 2026-10-16 — all variants
failed).

Verified recipe (2026-10-16) — the script sets it up automatically:

- dual-image edit with **image 1 = mannequin** (pose) and **image 2 = character** (identity);
- prompt `replace the pose of <image 2> with the pose of <image 1>. keep the character of <image 2>`;
- **VNCCS PoseStudio LoRA @ 1.0 is mandatory** — without it the mannequin is
  ignored entirely (3 no-LoRA controls);
- 25 steps, cfg 1, euler/simple, 1024 px. Single person, identity kept, pose
  follows the render; stable across seeds (sit ×3 seeds + crawling /
  kneel-side / lean-back all passed). Camera framing can differ slightly from
  the render; producing *new* mannequin renders still requires a route ④
  browser session — route ③ reuses captures you already have.

## 7. Route ④ — VNCCS PoseStudio (exact pose from the 3D library)

The `VNCCS_PoseStudio` node needs the ComfyUI **web frontend** for its 3D "live
capture"; the headless API fails with "Live capture timed out". So the runner
drives a CDP browser: load the official graph → set character image + pose
JSON → queue → collect outputs from disk. ~60–90 s each.

```bash
# list all 136 poses with resolved file paths
python3 scripts/run_vnccs_ui.py --list-poses

# run one pose on a character image (+ optional scene prompt)
python3 scripts/run_vnccs_ui.py --pose "squatting leaning back" \
  [--char /absolute/face.png] [--prompt "on a rooftop at night, city bokeh"] [--timeout 900]
```

- `--pose` takes the name/slug case-insensitively (`crawling`, `Squatting
  Leaning Back`, `arabesque`). 9 names exist in more than one repository
  (`Standing A`, `CloseUp A`, …); qualify with `<repo>/<category>/<name>`
  (exact keys printed by `--list-poses`, e.g.
  `miuproject_vnccs_poselibrary_main/standing/standing_a`).
- **Scene prompt (`--prompt`):** the capture prompt is rebuilt at execution
  time from the scene document's `export` block (default template
  `Draw character from image2\n<lighting>\n<user_prompt>`); `--prompt "..."`
  injects `export.user_prompt` before the graph loads. Editing the
  `TextEncodeQwenImage21` widget or adding `export.user_prompt` to a *library
  pose file* has no effect. To change the scene of an existing route ④ result,
  re-run it through route ② (`qwen_pose_test.py --mode edit`).
- The runner reaches a CDP browser through the OpenClaw adapter when present,
  otherwise through the bundled `scripts/browser_fallback.py` (reuses a
  reachable `COMFY_BROWSER_CDP` endpoint, else launches a throwaway headless
  Chromium; `COMFY_BROWSER_MODE=auto|attach|launch`).
- The runner re-indexes the pose library on every call — newly downloaded poses
  are usable immediately. Each run writes `<pose>_<stamp>.meta.json` next to
  the outputs and never clobbers previous results (unique comfy prefix per run).
- Output: `./outputs/vnccs_ui/` (override with `VNCCS_UI_OUT`). The 3D doll is a
  bare MakeHuman mannequin — nude prompts + pose transfer can produce nude
  output (expected: the model reads the doll's state).
- **Custom poses from code:** `scripts/make_custom_pose.py` loads a library
  pose into the PoseStudio editor, adds bone rotations, and saves through the
  editor's own Save (JSON + preview in
  `PoseLibrary/local_user_poses/poses/<category>/`). The new pose works with
  `run_vnccs_ui.py --pose` at once. `--list-bones` prints the base pose's
  euler angles; pass the full library id when a name is not unique.

  ```bash
  python3 scripts/make_custom_pose.py \
    --base "MIUProject__VNCCS_PoseLibrary_Main/poses/Standing/Standing A" \
    --name "Arms Out" --rotate upperarm_l:1:90 --rotate upperarm_r:1:-90
  ```
- **Pose fidelity caveat:** each pose JSON carries its own `cameraParams`
  (yaw/pitch/zoom); the generated image inherits that viewpoint. Poses whose
  shape only reads from another angle (e.g. a true arabesque's extended back
  leg) come out front-facing and ambiguous — rotate the doll in the UI and
  re-run, or pick a pose that reads from the front.

## 8. Environment & Safety

- ComfyUI as a service (original host: `systemctl --user status|restart
  comfyui.service`). After installing new custom nodes, one restart is required.
- The route scripts take the bundled media lock in shared mode
  (`media_lock(exclusive=False, wait_timeout=...)`) so they don't fight video
  jobs on a shared machine; route ④ wraps the whole browser run in it.
- On the original host, video tasks hold the lock exclusively (~06:45 / 09:00 /
  11:30 openclaw windows); expect waits, not conflicts.
- If a graph includes `QwenImage21Cache` and the host errors on it
  (`aimdo memory compile error`), remove the node and rewire LoRA → KSampler
  (the route ④ runner does this automatically in the browser).
- Never modify the workflow JSONs in this package's `workflows/` while a run is
  in flight; the harness works on in-memory copies anyway.
- A 50-step 1152×1728 run takes ~200–400 s on the int8 model; a 30-step edit
  run ~60–120 s.

## 9. Verification

1. Check the harness printed `ok: true` and the output file is non-empty.
2. Visually inspect with an image-reading tool (composition, pose match,
   anatomy, face). For pose-transfer runs, compare against the reference.
3. For reproductions of published images, compare side-by-side with the author
   original (`downloads/samples/*_author.jpg`; comparison-sheet
   example: `scripts/build_phase5_sheet.py`).
4. Record prompt/seed/steps/LoRA in the run's `*.json` meta file (harnesses
   write one automatically for routes ①②③④).
5. When a recipe deviation was made (weaker prompt, no LoRA, fewer steps,
   default seed), label the output and state the deviation next to it in the
   delivery message.

Last full verification: 2026-10-12 — route ① (4 author-prompt reproductions),
route ② (9/9 pose edits with identity preserved), route ④ (6 pose runs:
crawling, kneeling side, leaning back, sitting side, squatting leaning back,
arabesque — the last one verified for output only, pose-shape match unverified;
its doll capture turned out to be a stale legacy capture),
pose index count 136 == `GET /vnccs/pose_library/list`, pose-ladder A/B images
in `references/pose_examples/`.

Follow-up checks 2026-10-14: route ④ `--prompt` (scene follows the prompt, pose
preserved), bundled browser fallback launch path, and custom pose creation via
`scripts/make_custom_pose.py` (save + output verified).

Follow-up checks 2026-10-16 (route ③): 6 mannequin-reference transfers passed
(sit ×3 seeds, crawling, kneel-side, lean-back): single person, identity kept,
pose follows the render; 3 no-LoRA controls ignored the mannequin; photo and
illustration references still fail (composite / redraw of the reference
person). Script `scripts/run_pose_transfer.py` added and end-to-end tested.
