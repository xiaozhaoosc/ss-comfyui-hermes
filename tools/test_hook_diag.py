"""Quick diagnostic: trace NaN through UNet layers."""
import os, sys, torch, time
sys.path.insert(0, r'D:\ai_projects\ComfyUI')
sys.path.insert(0, r'D:\ai_projects\ComfyUI\custom_nodes\ComfyUI-IDM-VTON')

# GroupNorm fix
_orig_gn_fwd = torch.nn.GroupNorm.forward
def _safe_gn_fwd(self, x):
    return _orig_gn_fwd(self, x.float()).to(x.dtype)
torch.nn.GroupNorm.forward = _safe_gn_fwd

from diffusers import AutoencoderKL
from transformers import CLIPTextModel, CLIPTextModelWithProjection, AutoTokenizer
from src.idm_vton.unet_hacked_tryon import UNet2DConditionModel
from src.idm_vton.unet_hacked_garmnet import UNet2DConditionModel as UNet2DConditionModel_ref
import folder_paths
from torchvision import transforms
from PIL import Image

WP = os.path.join(folder_paths.models_dir, 'IDM-VTON')
dt = torch.float16
dev = 'cuda'

print('Loading...')
vae = AutoencoderKL.from_pretrained(WP, subfolder='vae', torch_dtype=dt).to(dev).eval()
unet = UNet2DConditionModel.from_pretrained(WP, subfolder='unet', torch_dtype=dt).to(dev).eval()
te2 = CLIPTextModelWithProjection.from_pretrained(WP, subfolder='text_encoder_2', torch_dtype=dt).to(dev).eval()
ue = UNet2DConditionModel_ref.from_pretrained(WP, subfolder='unet_encoder', torch_dtype=dt).to(dev).eval()
tok2 = AutoTokenizer.from_pretrained(WP, subfolder='tokenizer_2', use_fast=False)
print(f'GPU: {torch.cuda.memory_allocated()/1024**3:.1f}GB')

# Register hooks on first few ResNet blocks
nan_found = [False]
def make_hook(name):
    def hook(module, inp, out):
        if nan_found[0]:
            return
        if isinstance(out, tuple):
            out_t = out[0]
        else:
            out_t = out
        if torch.isnan(out_t).any():
            nan_pct = 100*torch.isnan(out_t).float().mean().item()
            print(f'[NAN] {name}: nan%={nan_pct:.1f}, out_range=[{out_t.float().min():.3f},{out_t.float().max():.3f}]')
            if isinstance(inp, tuple) and len(inp) > 0:
                inp_t = inp[0]
                if torch.isnan(inp_t).any():
                    print(f'  input already NaN')
                else:
                    print(f'  input clean: range=[{inp_t.float().min():.3f},{inp_t.float().max():.3f}]')
                    nan_found[0] = True
    return hook

# Hook first resnet and conv_in
unet.conv_in.register_forward_hook(make_hook('conv_in'))
for i, block in enumerate(unet.down_blocks):
    if hasattr(block, 'resnets'):
        for j, resnet in enumerate(block.resnets):
            resnet.register_forward_hook(make_hook(f'down[{i}].resnet[{j}]'))
            break  # Only first resnet per block
    break  # Only first down block

# Prepare input
w, h = 384, 512
tt = transforms.Compose([transforms.ToTensor(), transforms.Normalize([0.5], [0.5])])
garment = Image.open('input/todo/idm_vton_test/garment.jpg').convert('RGB').resize((w, h))
gt = tt(garment).unsqueeze(0).to(dev, dt)

tok_out = tok2('white t-shirt', return_tensors='pt', padding='max_length', max_length=77, truncation=True)
with torch.no_grad():
    pec = te2(tok_out.input_ids.to(dev))[0].to(dt)

cloth_latents = vae.encode(gt).latent_dist.sample() * vae.config.scaling_factor
cloth_latents = cloth_latents.to(dt)

t = torch.tensor([801], device=dev)
down, ref = ue(cloth_latents, t, pec, return_dict=False)
ref = list(ref)
ref_cfg = [torch.cat([torch.zeros_like(d), d]) for d in ref]

# Create UNet input
batch = 1
latent = torch.randn(batch, 4, h//8, w//8, device=dev, dtype=dt)
mask = torch.ones(batch, 1, h//8, w//8, device=dev, dtype=dt)
masked_latent = torch.randn(batch, 4, h//8, w//8, device=dev, dtype=dt)
pose_t = tt(Image.open('input/todo/vton_test/pose_dwpose.png').convert('RGB').resize((w, h))).unsqueeze(0).to(dev, dt)
pose_latents = vae.encode(pose_t).latent_dist.sample() * vae.config.scaling_factor
pose_latents = pose_latents.to(dt)

sample = torch.cat([
    torch.cat([latent, latent]),
    torch.cat([mask, mask]),
    torch.cat([masked_latent, masked_latent]),
    torch.cat([pose_latents, pose_latents]),
], dim=1)

prompt_embeds = torch.randn(2, 77, 2048, device=dev, dtype=dt)
add_time_ids = torch.tensor([[h, w, 0, 0, h, w]], device=dev, dtype=dt).repeat(2, 1)
add_text_embeds = torch.randn(2, 1280, device=dev, dtype=dt)

print(f'Running UNet forward...')
with torch.no_grad():
    out = unet(
        sample, t,
        encoder_hidden_states=prompt_embeds,
        added_cond_kwargs={"text_embeds": add_text_embeds, "time_ids": add_time_ids},
        return_dict=False,
        garment_features=ref_cfg,
    )[0]
    nan_pct = 100*torch.isnan(out).float().mean().item()
    print(f'UNet output: nan%={nan_pct:.1f}')
