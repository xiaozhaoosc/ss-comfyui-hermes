"""Minimal diagnostic: trace where NaN appears in UNet forward."""
import os, sys, torch, time
sys.path.insert(0, r'D:\ai_projects\ComfyUI')
sys.path.insert(0, r'D:\ai_projects\ComfyUI\custom_nodes\ComfyUI-IDM-VTON')

from diffusers import AutoencoderKL, DDPMScheduler
from transformers import AutoTokenizer, CLIPImageProcessor, CLIPVisionModelWithProjection, CLIPTextModel, CLIPTextModelWithProjection
from src.idm_vton.unet_hacked_tryon import UNet2DConditionModel
from src.idm_vton.unet_hacked_garmnet import UNet2DConditionModel as UNet2DConditionModel_ref
from src.idm_vton.tryon_pipeline import StableDiffusionXLInpaintPipeline as TryonPipeline
import folder_paths

WP = os.path.join(folder_paths.models_dir, 'IDM-VTON')
dt = torch.float16
dev = 'cuda'

t0 = time.time()
print('Loading models...')
vae = AutoencoderKL.from_pretrained(WP, subfolder='vae', torch_dtype=dt).to(dev).eval()
unet = UNet2DConditionModel.from_pretrained(WP, subfolder='unet', torch_dtype=dt).to(dev).eval()
te1 = CLIPTextModel.from_pretrained(WP, subfolder='text_encoder', torch_dtype=dt).to(dev).eval()
te2 = CLIPTextModelWithProjection.from_pretrained(WP, subfolder='text_encoder_2', torch_dtype=dt).to(dev).eval()
ie = CLIPVisionModelWithProjection.from_pretrained(WP, subfolder='image_encoder', torch_dtype=dt).to(dev).eval()
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
print(f'Loaded in {time.time()-t0:.0f}s. GPU: {torch.cuda.memory_allocated()/1024**3:.1f}GB')

from PIL import Image
from torchvision import transforms

w, h = 384, 512
tt = transforms.Compose([transforms.ToTensor(), transforms.Normalize([0.5], [0.5])])
garment = Image.open('input/todo/idm_vton_test/garment.jpg').convert('RGB').resize((w, h))
person = Image.open('input/todo/idm_vton_test/person.png').convert('RGB').resize((w, h))
mask_img = Image.open('input/todo/vton_test/mask_auto.png').convert('RGB').resize((w, h))
pose = Image.open('input/todo/vton_test/pose_dwpose.png').convert('RGB').resize((w, h))

garment_desc = 'white t-shirt'
negative_prompt = 'low quality, blurry'

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
    print(f'pe: {pe.shape}, pec: {pec.shape}')

    pt = tt(pose).unsqueeze(0).to(dev, dt)
    gt = tt(garment).unsqueeze(0).to(dev, dt)

    # VAE encode garment
    cloth_latents = pipe._encode_vae_image(gt, generator=torch.Generator(dev).manual_seed(42))
    print(f'cloth_latents: shape={cloth_latents.shape}, nan={torch.isnan(cloth_latents).any()}, range=[{cloth_latents.float().min():.3f},{cloth_latents.float().max():.3f}]')

    # Run unet_encoder
    t = torch.tensor([801], device=dev)
    down, ref = ue(cloth_latents, t, pec, return_dict=False)
    ref = list(ref)
    print(f'unet_encoder ref: {len(ref)}')
    for ri, r in enumerate(ref):
        nan_pct = 100*torch.isnan(r).float().mean().item()
        print(f'  ref[{ri}]: shape={r.shape}, nan%={nan_pct:.1f}, range=[{r.float().min():.3f},{r.float().max():.3f}]')

    # Run full pipeline with minimal steps
    print('\nRunning pipeline (1 step)...')
    result = pipe(
        prompt_embeds=pe, negative_prompt_embeds=npe,
        pooled_prompt_embeds=pp, negative_pooled_prompt_embeds=npp,
        num_inference_steps=10, generator=torch.Generator(dev).manual_seed(42),
        strength=1.0, pose_img=pt, text_embeds_cloth=pec,
        cloth=gt, mask_image=mask_img, image=person,
        height=h, width=w, ip_adapter_image=garment, guidance_scale=2.0,
    )
    images = result[0]
    os.makedirs('output', exist_ok=True)
    out_path = 'output/idm_vton_diag.png'
    if isinstance(images[0], Image.Image):
        images[0].save(out_path)
    else:
        out = transforms.ToPILImage()(images[0].cpu().permute(2, 0, 1) * 0.5 + 0.5)
        out.save(out_path)
    print(f'Saved: {out_path}')

print(f'Total: {time.time()-t0:.0f}s')
print(f'GPU peak: {torch.cuda.max_memory_allocated()/1024**3:.1f}GB')
