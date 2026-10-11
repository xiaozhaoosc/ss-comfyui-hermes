"""IDM-VTON inference test — clean version with correct UNet weights."""
import os, sys, torch, time
sys.path.insert(0, r'D:\ai_projects\ComfyUI')
sys.path.insert(0, r'D:\ai_projects\ComfyUI\custom_nodes\ComfyUI-IDM-VTON')

from diffusers import AutoencoderKL, DDPMScheduler
from transformers import (AutoTokenizer, CLIPImageProcessor,
    CLIPVisionModelWithProjection, CLIPTextModel, CLIPTextModelWithProjection)
from src.idm_vton.unet_hacked_tryon import UNet2DConditionModel
from src.idm_vton.unet_hacked_garmnet import UNet2DConditionModel as UNet2DConditionModel_ref
from src.idm_vton.tryon_pipeline import StableDiffusionXLInpaintPipeline as TryonPipeline

WP = os.path.join('models', 'IDM-VTON')
dt = torch.float16
dev = 'cuda'

t0 = time.time()
print('[1/5] Loading models...')
vae = AutoencoderKL.from_pretrained(WP, subfolder='vae', torch_dtype=dt).to(dev).eval()
unet = UNet2DConditionModel.from_pretrained(WP, subfolder='unet', torch_dtype=dt).to(dev).eval()
ie = CLIPVisionModelWithProjection.from_pretrained(WP, subfolder='image_encoder', torch_dtype=dt).to(dev).eval()
te1 = CLIPTextModel.from_pretrained(WP, subfolder='text_encoder', torch_dtype=dt).to(dev).eval()
te2 = CLIPTextModelWithProjection.from_pretrained(WP, subfolder='text_encoder_2', torch_dtype=dt).to(dev).eval()
ue = UNet2DConditionModel_ref.from_pretrained(WP, subfolder='unet_encoder', torch_dtype=dt).to(dev).eval()
tok1 = AutoTokenizer.from_pretrained(WP, subfolder='tokenizer', use_fast=False)
tok2 = AutoTokenizer.from_pretrained(WP, subfolder='tokenizer_2', use_fast=False)
sched = DDPMScheduler.from_pretrained(WP, subfolder='scheduler')

pipe = TryonPipeline.from_pretrained(
    WP, unet=unet, vae=vae, feature_extractor=CLIPImageProcessor(),
    text_encoder=te1, text_encoder_2=te2, tokenizer=tok1, tokenizer_2=tok2,
    scheduler=sched, image_encoder=ie, torch_dtype=dt,
)
pipe.unet_encoder = ue
pipe = pipe.to(dev)
pipe.weight_dtype = dt
print(f'  Loaded in {time.time()-t0:.0f}s. GPU: {torch.cuda.memory_allocated()/1024**3:.1f}GB')

print('[2/5] Loading inputs...')
from PIL import Image
from torchvision import transforms

w, h = 384, 512
tt = transforms.Compose([transforms.ToTensor(), transforms.Normalize([0.5], [0.5])])

# Use the test images
person = Image.open('input/vton/person.png').convert('RGB').resize((w, h))
garment = Image.open('input/vton/garment.jpg').convert('RGB').resize((w, h))
mask_img = Image.open('input/todo/vton_test/mask_auto.png').convert('RGB').resize((w, h))
pose = Image.open('input/todo/vton_test/pose_dwpose.png').convert('RGB').resize((w, h))
print(f'  person={person.size}, garment={garment.size}, mask={mask_img.size}, pose={pose.size}')

garment_desc = 'white t-shirt'
negative_prompt = 'low quality, blurry'

print('[3/5] Encoding prompts...')
with torch.no_grad(), torch.amp.autocast('cuda'), torch.inference_mode():
    prompt = 'model is wearing ' + garment_desc
    (pe, npe, pp, npp) = pipe.encode_prompt(
        prompt=prompt, device=torch.device(dev),
        num_images_per_prompt=1, do_classifier_free_guidance=True,
        negative_prompt=negative_prompt,
    )
    prompt_c = ['a photo of ' + garment_desc]
    (pec, _, _, _) = pipe.encode_prompt(
        prompt=prompt_c, device=torch.device(dev),
        num_images_per_prompt=1, do_classifier_free_guidance=False,
        negative_prompt=[negative_prompt],
    )
    print(f'  Encoded. GPU: {torch.cuda.memory_allocated()/1024**3:.1f}GB')

    pt = tt(pose).unsqueeze(0).to(dev, dt)
    gt = tt(garment).unsqueeze(0).to(dev, dt)

    print('[4/5] Running inference (5 steps, 384x512)...')
    t2 = time.time()
    result = pipe(
        prompt_embeds=pe, negative_prompt_embeds=npe,
        pooled_prompt_embeds=pp, negative_pooled_prompt_embeds=npp,
        num_inference_steps=5, generator=torch.Generator(dev).manual_seed(42),
        strength=0.9, pose_img=pt, text_embeds_cloth=pec,
        cloth=gt, mask_image=mask_img, image=person,
        height=h, width=w, ip_adapter_image=garment, guidance_scale=2.0,
    )
    images = result[0]
    print(f'  Inference: {time.time()-t2:.0f}s')

print('[5/5] Saving output...')
os.makedirs('output', exist_ok=True)
out_path = 'output/idm_vton_test_clean.png'
if isinstance(images[0], Image.Image):
    images[0].save(out_path)
else:
    out = transforms.ToPILImage()(images[0].cpu().permute(2, 0, 1) * 0.5 + 0.5)
    out.save(out_path)

import numpy as np
arr = np.array(Image.open(out_path))
mean_val = arr.mean()
print(f'  Mean pixel: {mean_val:.1f}')
if mean_val < 5:
    print('  [WARN] Output is mostly black!')
elif mean_val > 250:
    print('  [WARN] Output is mostly white!')
else:
    print('  [OK] Output looks valid!')

print(f'\nTotal: {time.time()-t0:.0f}s')
print(f'GPU peak: {torch.cuda.max_memory_allocated()/1024**3:.1f}GB')
print(f'Saved: {out_path}')
