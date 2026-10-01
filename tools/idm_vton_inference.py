"""
IDM-VTON standalone inference script.
Bypasses ComfyUI node system - directly loads and runs the pipeline.
"""
import os
import sys

# Setup paths
COMFY_ROOT = r"D:\ai_projects\ComfyUI"
sys.path.insert(0, COMFY_ROOT)
sys.path.insert(0, os.path.join(COMFY_ROOT, "custom_nodes", "ComfyUI-IDM-VTON"))

import torch
import numpy as np
from PIL import Image
from torchvision import transforms
from diffusers import AutoencoderKL, DDPMScheduler
from transformers import (
    AutoTokenizer, CLIPImageProcessor,
    CLIPVisionModelWithProjection, CLIPTextModelWithProjection, CLIPTextModel,
)

# IDM-VTON imports
from src.idm_vton.unet_hacked_tryon import UNet2DConditionModel
from src.idm_vton.unet_hacked_garmnet import UNet2DConditionModel as UNet2DConditionModel_ref
from src.idm_vton.tryon_pipeline import StableDiffusionXLInpaintPipeline as TryonPipeline

import folder_paths
from comfy.model_management import get_torch_device

WEIGHTS_PATH = os.path.join(folder_paths.models_dir, "IDM-VTON")
DEVICE = get_torch_device()

print(f"[IDM-VTON] WEIGHTS_PATH: {WEIGHTS_PATH}")
print(f"[IDM-VTON] DEVICE: {DEVICE}")


def load_pipeline(weight_dtype=torch.float16):
    """Load all IDM-VTON models with CPU offloading."""
    print("[IDM-VTON] Loading scheduler...")
    noise_scheduler = DDPMScheduler.from_pretrained(WEIGHTS_PATH, subfolder="scheduler")

    print("[IDM-VTON] Loading VAE...")
    vae = AutoencoderKL.from_pretrained(
        WEIGHTS_PATH, subfolder="vae", torch_dtype=weight_dtype
    ).requires_grad_(False).eval()

    print("[IDM-VTON] Loading UNet...")
    unet = UNet2DConditionModel.from_pretrained(
        WEIGHTS_PATH, subfolder="unet", torch_dtype=weight_dtype
    ).requires_grad_(False).eval()

    print("[IDM-VTON] Loading image encoder...")
    image_encoder = CLIPVisionModelWithProjection.from_pretrained(
        WEIGHTS_PATH, subfolder="image_encoder", torch_dtype=weight_dtype
    ).requires_grad_(False).eval()

    print("[IDM-VTON] Loading UNet encoder...")
    unet_encoder = UNet2DConditionModel_ref.from_pretrained(
        WEIGHTS_PATH, subfolder="unet_encoder", torch_dtype=weight_dtype
    ).requires_grad_(False).eval()

    print("[IDM-VTON] Loading text encoders...")
    text_encoder_one = CLIPTextModel.from_pretrained(
        WEIGHTS_PATH, subfolder="text_encoder", torch_dtype=weight_dtype
    ).requires_grad_(False).eval()

    text_encoder_two = CLIPTextModelWithProjection.from_pretrained(
        WEIGHTS_PATH, subfolder="text_encoder_2", torch_dtype=weight_dtype
    ).requires_grad_(False).eval()

    print("[IDM-VTON] Loading tokenizers...")
    tokenizer_one = AutoTokenizer.from_pretrained(
        WEIGHTS_PATH, subfolder="tokenizer", revision=None, use_fast=False
    )
    tokenizer_two = AutoTokenizer.from_pretrained(
        WEIGHTS_PATH, subfolder="tokenizer_2", revision=None, use_fast=False
    )

    print("[IDM-VTON] Building pipeline...")
    pipe = TryonPipeline.from_pretrained(
        WEIGHTS_PATH,
        unet=unet, vae=vae,
        feature_extractor=CLIPImageProcessor(),
        text_encoder=text_encoder_one, text_encoder_2=text_encoder_two,
        tokenizer=tokenizer_one, tokenizer_2=tokenizer_two,
        scheduler=noise_scheduler, image_encoder=image_encoder,
        torch_dtype=weight_dtype,
    )
    pipe.unet_encoder = unet_encoder

    # CPU offload for 16GB VRAM
    pipe.enable_model_cpu_offload()
    pipe.weight_dtype = weight_dtype
    print("[IDM-VTON] Pipeline ready!")
    return pipe


def run_tryon(pipe, person_path, garment_path, mask_path, pose_path,
              garment_description="white t-shirt",
              negative_prompt="low quality, blurry, distorted",
              width=768, height=1024,
              num_inference_steps=20, guidance_scale=2.0,
              strength=0.9, seed=42):
    """Run virtual try-on inference."""
    # Load images
    human_img = Image.open(person_path).convert("RGB").resize((width, height))
    garment_img = Image.open(garment_path).convert("RGB").resize((width, height))
    mask_img = Image.open(mask_path).convert("RGB").resize((width, height))
    pose_img = Image.open(pose_path).convert("RGB").resize((width, height))

    tensor_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.5], [0.5]),
    ])

    with torch.no_grad(), torch.cuda.amp.autocast(), torch.inference_mode():
        # Encode prompts
        prompt = "model is wearing " + garment_description
        (prompt_embeds, negative_prompt_embeds,
         pooled_prompt_embeds, negative_pooled_prompt_embeds) = pipe.encode_prompt(
            prompt, num_images_per_prompt=1,
            do_classifier_free_guidance=True,
            negative_prompt=negative_prompt,
        )

        prompt_c = ["a photo of " + garment_description]
        prompt_embeds_c, _, _, _ = pipe.encode_prompt(
            prompt_c, num_images_per_prompt=1,
            do_classifier_free_guidance=False,
            negative_prompt=[negative_prompt],
        )

        pose_tensor = tensor_transform(pose_img).unsqueeze(0).to(DEVICE, pipe.dtype)
        garment_tensor = tensor_transform(garment_img).unsqueeze(0).to(DEVICE, pipe.dtype)

        print("[IDM-VTON] Running inference...")
        images = pipe(
            prompt_embeds=prompt_embeds,
            negative_prompt_embeds=negative_prompt_embeds,
            pooled_prompt_embeds=pooled_prompt_embeds,
            negative_pooled_prompt_embeds=negative_pooled_prompt_embeds,
            num_inference_steps=num_inference_steps,
            generator=torch.Generator(DEVICE).manual_seed(seed),
            strength=strength,
            pose_img=pose_tensor,
            text_embeds_cloth=prompt_embeds_c,
            cloth=garment_tensor,
            mask_image=mask_img,
            image=human_img,
            height=height, width=width,
            ip_adapter_image=garment_img,
            guidance_scale=guidance_scale,
        )[0]

    return images


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--person", required=True)
    parser.add_argument("--garment", required=True)
    parser.add_argument("--mask", required=True)
    parser.add_argument("--pose", required=True)
    parser.add_argument("--output", default="output/idm_vton_result.png")
    parser.add_argument("--description", default="white t-shirt")
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    pipe = load_pipeline()
    result = run_tryon(
        pipe, args.person, args.garment, args.mask, args.pose,
        garment_description=args.description,
        width=args.width, height=args.height,
        num_inference_steps=args.steps, seed=args.seed,
    )

    # Save result
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    out_img = transforms.ToPILImage()(result[0].cpu().permute(2, 0, 1) * 0.5 + 0.5)
    out_img.save(args.output)
    print(f"[IDM-VTON] Saved: {args.output}")
