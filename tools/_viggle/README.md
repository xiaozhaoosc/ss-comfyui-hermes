---
license: other
license_name: qwen-research
license_link: LICENSE
base_model: Qwen/Qwen-Image-2.1
base_model_relation: adapter
library_name: diffusers
pipeline_tag: text-to-image
tags:
  - diffusers
  - lora
  - text-to-image
  - image-to-image
  - image-editing
  - distillation
  - dmd
  - turbo
  - few-step
  - qwen-image
  - comfyui
---

# Qwen-Image-2.1-viggle-turbo — v0.2.1

**Built with Qwen.** A few-step distilled student of [Qwen/Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1),
trained by Viggle with Distribution Matching Distillation. It does both text-to-image and instruction-driven editing
with 1–3 reference images in **6 transformer passes instead of 40**, with **no classifier-free guidance**.

<video controls autoplay muted loop playsinline width="100%"
  src="https://huggingface.co/Viggle/Qwen-Image-2.1-viggle-turbo/resolve/main/assets/viggle_turbo_promo.mp4"></video>

About **5× faster** than the 40-step base model end to end, and **very competitive with it in quality**: on the
official Qwen examples the two are hard to tell apart on most prompts. The clearest gap is small, dense text, where the
base model is still ahead (8 steps narrows it). See for yourself in the **Comparison** tab of the
[demo Space](https://huggingface.co/spaces/Viggle/Qwen-Image-2.1-viggle-turbo): 32 examples of the
[Qwen/Qwen-Image-2.1 Space](https://huggingface.co/spaces/Qwen/Qwen-Image-2.1), turbo in 6 steps (and 8 on the 5
dense-text examples) vs base in 40 steps, same prompt, inputs and seed, one sample each, in an image slider. Complicated edits can still fall short of the base
model ([Known limitations](#known-limitations)).

**v0.2.1 (2026-09-24) — use this one:**

* **`Qwen-Image-2.1-viggle-turbo-v0.2.1-6step-lora-r256.safetensors` — LoRA adapter** (rank 256, alpha 256, bf16, 1.3 GB)
  loaded on top of the base transformer at runtime. Sample it with **6 steps on the shipped sigma nodes**
  `sigmas=[1.0, 0.9375, 0.875, 0.75, 0.5, 0.25]` (see Usage). This is what the
  [demo Space](https://huggingface.co/spaces/Viggle/Qwen-Image-2.1-viggle-turbo) runs.
* `Qwen-Image-2.1-viggle-turbo-v0.2.1-6step-lora-r128.safetensors` — the same adapter cut to rank 128 (alpha 128, 680 MB),
  used by the [ComfyUI workflows](#comfyui). Same usage as r256; see [rank 128](#rank-128) for how close it is.

**ComfyUI:** custom nodes and ready-made text-to-image / edit workflows are in
[`comfyui/`](https://huggingface.co/Viggle/Qwen-Image-2.1-viggle-turbo/tree/main/comfyui); setup is in [ComfyUI](#comfyui).
Honest caveat: I am not a regular ComfyUI user, and the port was mostly vibe-coded with an AI coding assistant. It
was checked against the diffusers pipeline (numbers in the ComfyUI section) and runs end to end, but expect rough
edges. Issues and fixes from people who know ComfyUI better are very welcome.

v0.2.1 is the step-700 checkpoint of the run whose step-600 checkpoint shipped as v0.2 on 2026-09-23: 100 more
training steps, same recipe, same 6-step schedule. Against v0.2 it is a little sharper (Laplacian sharpness 0.0199
vs 0.0187) and marginally more diverse (0.98× vs 0.97× the base model), with the same 0% composition drift. The v0.2
files (`Qwen-Image-2.1-viggle-turbo-v0.2-5step-lora-r256.safetensors`, the r128 cut, `peft_v0.2/`) stay in the repository unchanged;
sample them with the same 6-step nodes (the `5step` in their name is the schedule they launched with, see
[Rules that matter](#rules-that-matter)).

What changed against v0.1, measured on our held-out set of 96 user requests (text-to-image and editing) against the
40-step base model with its official prompt enhancement:

| | v0.1 LoRA r64 | v0.1 full fine-tune | **v0.2.1 LoRA r256, 6 steps** | v0.2 LoRA r256, 6 steps | (v0.2 at 5 steps) | (v0.2 at 4 steps) |
|---|---|---|---|---|---|---|
| sample diversity, × base model ¹ | 0.75 | 0.72 | **0.98** | 0.97 | 0.93 | 0.89 |
| composition drift vs base model ² | −0.019 | −0.033 | **+0.000** | −0.001 | +0.000 | +0.002 |
| prompts whose layout differs from the base model ³ | — | — | **0%** | 0% | 4% | — |

¹ mean intra-prompt DINOv2 patch distance over 8 seeds per prompt, 32 prompts, as a ratio to the 40-step base model
(1.00 = as diverse as the base). v0.1 collapsed seeds onto near-identical layouts; v0.2 keeps the base model's spread.
² mean horizontal drift of the image centroid relative to the base model's output for the same prompt and seed, in
image widths; 0 means the student places its subjects where the base model does.
³ share of the 96 prompts where the student's composition visibly differs from the base model's for the same seed
(centroid drift above 0.05 image widths). In practice v0.2 and v0.2.1 follow the prompt
and the reference images noticeably more faithfully than v0.1 — fewer dropped or merged instructions, less ghosting
of duplicated subjects — and match the base model's sharpness where the v0.1 LoRA was softer.

The v0.2 files and the v0.1 artifacts (`transformer/` full fine-tune and the r64 LoRA, both 4-step) stay in the
repository unchanged for reproducibility; there is no reason to prefer them.

> **Known limits.** Complicated edits (multi-reference composition, face swaps, identity-preserving edits, instructions
> with several constraints) can still fall short of the 40-step base model. We will keep updating this repository as
> the distillation improves.

## What's inside

```
Qwen-Image-2.1-viggle-turbo-v0.2.1-6step-lora-r256.safetensors # v0.2.1 LoRA (rank 256, alpha 256), diffusers key format, bf16  <- use this
peft_v0.2.1/                                                   # the same v0.2.1 adapter in peft key format, F32 as trained
Qwen-Image-2.1-viggle-turbo-v0.2.1-6step-lora-r128.safetensors # v0.2.1 LoRA truncated to rank 128 (alpha 128), diffusers key format, bf16
comfyui/                                                       # ComfyUI custom nodes (viggle_turbo.py), text-to-image and edit workflows, example inputs
scheduler/scheduler_config.json                                # base scheduler config with shift_terminal: null
Qwen-Image-2.1-viggle-turbo-v0.2-5step-lora-r256.safetensors   # v0.2 LoRA (step 600 of the same run), kept for reference
Qwen-Image-2.1-viggle-turbo-v0.2-5step-lora-r128.safetensors   # v0.2 LoRA truncated to rank 128, kept for reference
peft_v0.2/                                                     # v0.2 adapter in peft key format, F32
Qwen-Image-2.1-viggle-turbo-4step-lora-r64.safetensors         # v0.1 LoRA (rank 64), 4-step, kept for reference
peft/                                                          # v0.1 adapter in peft key format, F32
transformer/                                                   # v0.1 full fine-tuned transformer (bf16), 4-step, kept for reference
LICENSE, NOTICE, README.md
```

Shipped checkpoint: v0.2.1 is the step-700 EMA student (v0.2 was step 600) of a LoRA run (rank 256 on the attention, image-MLP, modulation and
timestep-embedder projections) that adds SenseFlow-style intra-segment guidance (the student's velocity over each of its
segments is regressed on the teacher's) and prompt-enhanced teacher targets to the DMD objective;
it was trained on the 4-step schedule and is sampled with the first (highest-noise) segment cut into three (6 steps),
which removes the detail loss, ghosting and composition drift of the plain 4-step rollout (5 steps, the segment cut in
two, was the launch schedule; 6 is strictly better on every metric we track, with the same weights). The LoRA is never merged into the transformer — merging into
bf16 is lossy, loading it at runtime is exact. Text encoder, VAE and processor are not redistributed; they load from the base repo.

## Install

```bash
pip install -U torch "transformers>=5.17,<6" accelerate safetensors peft pillow
pip install "git+https://github.com/huggingface/diffusers.git@80c7ed262aeffbeb43ef13ae04baeb9b84515a69"
```

`QwenImage21Pipeline` is not in a released `diffusers` yet, hence the pinned git install. `peft` is required.

## Usage

### Load the v0.2.1 LoRA

```python
import torch
from diffusers import QwenImage21Pipeline, FlowMatchEulerDiscreteScheduler

pipe = QwenImage21Pipeline.from_pretrained("Qwen/Qwen-Image-2.1", dtype=torch.bfloat16)
pipe.load_lora_weights(
    "Viggle/Qwen-Image-2.1-viggle-turbo",
    weight_name="Qwen-Image-2.1-viggle-turbo-v0.2.1-6step-lora-r256.safetensors",
)
pipe.scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(
    "Viggle/Qwen-Image-2.1-viggle-turbo", subfolder="scheduler"
)
pipe.to("cuda")

STEPS, SIGMAS = 6, [1.0, 0.9375, 0.875, 0.75, 0.5, 0.25]   # the v0.2.1 schedule; pass both to every call
```

<details>
<summary>v0.1 students (4-step, for reference)</summary>

```python
# v0.1 full fine-tuned transformer
from diffusers import QwenImage21Transformer2DModel
transformer = QwenImage21Transformer2DModel.from_pretrained(
    "Viggle/Qwen-Image-2.1-viggle-turbo", subfolder="transformer", torch_dtype=torch.bfloat16
)
pipe = QwenImage21Pipeline.from_pretrained("Qwen/Qwen-Image-2.1", transformer=transformer, dtype=torch.bfloat16)
# v0.1 LoRA
pipe.load_lora_weights("Viggle/Qwen-Image-2.1-viggle-turbo", weight_name="Qwen-Image-2.1-viggle-turbo-4step-lora-r64.safetensors")
# both: the shipped scheduler as above, then num_inference_steps=4 and no sigmas= argument
```

Never stack two students (a LoRA on top of the fine-tuned transformer, or both LoRAs).
</details>

### Text to image

```python
image = pipe(
    prompt="A studio portrait of an old fisherman mending a net, warm rim light, 85mm.",
    height=1024,
    width=1024,
    num_inference_steps=STEPS,
    sigmas=SIGMAS,
    true_cfg_scale=1.0,                                   # no CFG (also the default)
    generator=torch.Generator("cuda").manual_seed(0),
).images[0]
image.save("out.png")
```

### Image editing (1–3 reference images)

```python
from diffusers.utils import load_image

image = pipe(                                             # same pipe object as above
    prompt="Replace the background with a sunset beach, keep the subject unchanged.",
    image=[load_image("input.png")],                      # list; order fixes <image1>, <image2>, ...
    output_resolution=1024,
    num_inference_steps=STEPS,
    sigmas=SIGMAS,
    true_cfg_scale=1.0,
    generator=torch.Generator("cuda").manual_seed(0),
).images[0]
```

### Rules that matter

* **`num_inference_steps=6` with `sigmas=[1.0, 0.9375, 0.875, 0.75, 0.5, 0.25]`, `true_cfg_scale=1.0`, no negative prompt.**
  These are *raw* sigma nodes: the pipeline applies its resolution-dependent time shift to them exactly as it does to
  its default nodes, so pass them as written for every resolution. They are the 4-step training nodes
  `linspace(1, 1/4, 4)` with the first (highest-noise) segment `1 → 0.75` cut into three. `num_inference_steps=4` without
  `sigmas=` is the training schedule and also works, with slightly less detail and diversity (table above).
* **If you change the step count, add or remove steps at the high-noise end only.** The composition is decided
  between raw sigma 1 and 0.875 (after the shift, roughly the first 5% of the noise range at 1024²), and one big Euler
  step there ghosts and drifts the layout; the low-noise nodes `0.75, 0.5, 0.25` are the ones the student was trained
  to land on, and moving them (a 6-step `[1, 0.958, 0.917, 0.875, 0.625, 0.375]`) makes every image visibly softer
  (Laplacian sharpness 0.014 against 0.020). So keep `0.875, 0.75, 0.5, 0.25` and split `1 → 0.875` evenly:
  5 steps `[1, 0.875, 0.75, 0.5, 0.25]` (the launch schedule, 4% of prompts drift), 6 as above (0%), 7
  `[1, 0.9583, 0.9167, 0.875, 0.75, 0.5, 0.25]` (also 0%, marginally sharper, not visibly better than 6). Uniform
  `linspace` schedules with other step counts, and CFG, do not help.
* **Use the shipped scheduler config** (or `FlowMatchEulerDiscreteScheduler.from_config(pipe.scheduler.config,
  shift_terminal=None)`). The base config's `shift_terminal: 0.02` would wreck the last step.
* **Leave the LoRA scale at 1.0** (alpha equals rank).
* Reference-image order determines which image `image 1` / `image 2` in the prompt refers to. Without
  `height`/`width`, the output aspect ratio follows the **last** reference (in ComfyUI: the **first**). Up to 3
  references were used in training.
* Prompt rewriting with the official
  [PE-T2I](https://huggingface.co/Qwen/Qwen-Image-2.1-PE-T2I) / [PE-I2I](https://huggingface.co/Qwen/Qwen-Image-2.1-PE-I2I)
  rewriters is recommended: the student was distilled against prompt-enhanced teacher targets, and the rewriters help
  composition and rendered text. The numbers above use them. Raw prompts work too.
* `peft` users can load `peft_v0.2.1/` directly:
  `pipe.transformer.load_lora_adapter("Viggle/Qwen-Image-2.1-viggle-turbo", subfolder="peft_v0.2.1", weight_name="adapter_model.safetensors", prefix=None)`
  — same weights, different key names; pick one path, not both.

### Resolutions

Training sizes follow the base model's `calculate_dimensions(area, aspect_ratio)` rounded to a multiple of 32.
Text-to-image was trained at 1024² and 2048² area, editing at 1024² and 1536² area (references always encoded at 1024²
area). Other sizes work; these are where the training mass sits.

| ratio | 1024² area (T2I + editing) | 1536² area (editing) | 2048² area (T2I) |
|---|---|---|---|
| 1:1  | 1024 × 1024 | 1536 × 1536 | 2048 × 2048 |
| 4:3  | 1184 × 896  | 1760 × 1344 | 2368 × 1760 |
| 3:4  | 896 × 1184  | 1344 × 1760 | 1760 × 2368 |
| 16:9 | 1376 × 768  | 2048 × 1152 | 2720 × 1536 |
| 9:16 | 768 × 1376  | 1152 × 2048 | 1536 × 2720 |
| 3:2  | 1248 × 832  | 1888 × 1248 | 2496 × 1664 |
| 2:3  | 832 × 1248  | 1248 × 1888 | 1664 × 2496 |

### Rank 128

`...-lora-r128.safetensors` is the r256 adapter truncated by an exact per-layer SVD of its update `ΔW = B A`, which is
the best rank-128 approximation (Eckart–Young). Per layer it keeps 83–100% of the update's energy (median 95%); what it
drops is below 0.05% of the base weight. On the 96 held-out requests, with the same noise and prompts, its images differ
from the r256 adapter's by LPIPS 0.0244. Re-factoring the r256 adapter at full rank, which changes nothing but float
round-off, already moves them by 0.0239, so r128 sits at that noise floor (rank 64: 0.0267). The LPIPS numbers were
measured on the v0.2 pair; the v0.2.1 truncation has the same spectrum (83–100% of the energy kept per layer, median 95%).

## ComfyUI

> The ComfyUI port is mostly vibe-coded: I don't use ComfyUI day to day, and the nodes and workflows were written
> largely with an AI coding assistant. What was verified: the sigma schedule matches diffusers to float precision, and the
> image gap to diffusers is in the table below. Workflow ergonomics and less common setups were not tested much;
> please open a discussion if something looks wrong.

Tested with ComfyUI 0.37.0 (frontend 1.53.6), which has native Qwen-Image-2.1 support. In [`comfyui/`](comfyui):

* `viggle_turbo.py` — two custom nodes. Copy it into `ComfyUI/custom_nodes/` and restart ComfyUI.
* `Qwen-Image-2.1-viggle-turbo-t2i.json`, `Qwen-Image-2.1-viggle-turbo-edit.json` — the workflows (drag into ComfyUI).
  Each has a note with the settings and an optional prompt-enhancer group.
* `input/woman2.webp`, `input/cat.webp` — the edit workflow's example references; copy them into `ComfyUI/input/`.
  Like the reference photos in the [demo Space](https://huggingface.co/spaces/Viggle/Qwen-Image-2.1-viggle-turbo), they come from the
  [black-forest-labs/flux-klein-9b-kv](https://huggingface.co/spaces/black-forest-labs/flux-klein-9b-kv) Space.

Model files (the workflows carry their download links):

| ComfyUI folder | file | size |
|---|---|---|
| `diffusion_models/` | [`qwen_image_2.1_int8_convrot.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image-2.1) or `qwen_image_2.1_bf16.safetensors` | 7.3 / 14.2 GB |
| `text_encoders/` | [`qwen3vl_8b_int8_convrot.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image-2.1) or `qwen3vl_8b_bf16.safetensors` | 9.4 / 17.5 GB |
| `vae/` | [`qwen_image_2.1_vae_bf16.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image-2.1) | 0.7 GB |
| `loras/` | `Qwen-Image-2.1-viggle-turbo-v0.2.1-6step-lora-r128.safetensors` (this repo) or the r256 file | 0.7 / 1.4 GB |

The base files are Comfy-Org's, the ones ComfyUI's own Qwen-Image-2.1 template uses. The workflows default to the int8
transformer and text encoder, the r128 LoRA and the prompt enhancer on; with every model kept loaded this peaks at
26 GB of VRAM on a 1248 × 832 image. The bf16 files are a drop-in swap.

The two nodes:

* **Viggle Turbo Sigmas** — the 6-step schedule above with the pipeline's resolution-dependent shift (the `nodes`
  field takes any raw schedule; see [Rules that matter](#rules-that-matter) before changing it). Use it instead
  of a KSampler scheduler; with euler and `BasicGuider` (no CFG, no negative prompt).
* **Viggle Turbo LoRA (unmerged)** — applies the LoRA at runtime as `W x + B A x`, as diffusers does. ComfyUI's stock
  LoRA loaders merge it into the weights instead, and for this adapter the merge is lossy: round-to-nearest into bf16
  keeps about 70% of the update on average (about 40% in some early MLP layers), and requantizing the int8 weights
  keeps it on average but adds noise about 4× its size. LPIPS distance from diffusers with the r256 LoRA, on 5
  requests with the same noise:

  | ComfyUI transformer | stock LoRA loader (merged) | Viggle Turbo LoRA (unmerged) | no LoRA on either side |
  |---|---|---|---|
  | bf16 | 0.093 | 0.052 | 0.033 |
  | int8 | 0.086 | 0.038 | 0.045 |

  The last column is the gap ComfyUI and diffusers have without any LoRA. The unmerged node costs about 10–25% more
  time per step. Keep its strength at 1.0.

Differences from diffusers: in the edit workflow the output size follows **image 1**, at about 1 MP (diffusers follows
the last reference). The prompt enhancer uses the Qwen3-VL text encoder with the official rewriter system prompts; the
edit rewriter sees image 1 and image 2.

**Troubleshooting:** with `comfy_kitchen` 0.2.35 on an NVIDIA driver older than 580, `TextGenerate` (the prompt
enhancer) fails with a CUDA driver error from comfy_kitchen's CUDA 13 kernels. Update the driver, or turn *Enhance
prompt* off; image generation itself does not use that code path.

## Known limitations

v0.2.1 is very competitive with the base model on text-to-image and on most edits, but still falls short of it on
complicated editing. Specifically:

* **Complicated edits degrade**: multi-reference composition, face swaps and identity-document edits can still produce
  duplicated or ghosted figures; "keep everything the same" requests can drift in identity. Much rarer than in v0.1.
* **Small or long rendered text can garble** more often than with the 40-step base model.
* **2K output is compared with the base model only by eye** (the text-to-image examples of the Comparison tab are
  ~4 MP); none of the numbers above are at 2K.
* RGBA output, mask-guided editing and edits with 5, 6 and 10 reference images work on the Qwen examples in the
  Comparison tab but are not measured.
* On the dense-text examples, **8 steps** (`sigmas=[1, 0.9375, 0.875, 0.75, 0.625, 0.5, 0.25, 0.125]`) prints small text
  noticeably cleaner than 6; the Comparison tab shows both.
* The two metrics above are our own, computed on 96 / 32 held-out user requests; no standard benchmark is claimed.

## License

This model is a derivative work of Qwen-Image-2.1 and is distributed under the **Qwen RESEARCH LICENSE AGREEMENT**
([`LICENSE`](LICENSE)): **non-commercial use only** — research or evaluation purposes. Commercial use requires a
separate licence from the licensor (`model-business@notice.qwencloud.com`). See [`NOTICE`](NOTICE) for the required
attribution.

> Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT, Copyright (c) 2026 Hangzhou Tongyi Laboratory Technology
> Co., Ltd. All Rights Reserved.

Relative to [`Qwen/Qwen-Image-2.1`](https://huggingface.co/Qwen/Qwen-Image-2.1) this repository **adds** LoRA
adapters (v0.2.1 and v0.2 at rank 256 and 128, v0.1), ComfyUI nodes, workflows and two example input photos, and a scheduler config with `shift_terminal`
changed from `0.02` to `null`, and ships a **modified transformer** (`transformer/`, the v0.1 full fine-tune); text
encoder, VAE and processor are not redistributed.

Distillation method: DMD2 (Yin et al., 2024) / SenseFlow-style distribution matching. Distillation and release by
**Viggle**. **Built with Qwen.**
