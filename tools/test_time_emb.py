"""Diagnose time_emb_proj Linear overflow."""
import os, sys, torch
sys.path.insert(0, r'D:\ai_projects\ComfyUI')
sys.path.insert(0, r'D:\ai_projects\ComfyUI\custom_nodes\ComfyUI-IDM-VTON')

# GroupNorm fix
_orig_gn_fwd = torch.nn.GroupNorm.forward
def _safe_gn_fwd(self, x):
    x_f32 = x.float()
    w = self.weight.float() if self.weight is not None else None
    b = self.bias.float() if self.bias is not None else None
    return torch.nn.functional.group_norm(x_f32, self.num_groups, w, b, self.eps).to(x.dtype)
torch.nn.GroupNorm.forward = _safe_gn_fwd

from src.idm_vton.unet_hacked_tryon import UNet2DConditionModel
import folder_paths

WP = os.path.join(folder_paths.models_dir, 'IDM-VTON')
dt = torch.float16
dev = 'cuda'

unet = UNet2DConditionModel.from_pretrained(WP, subfolder='unet', torch_dtype=dt).to(dev).eval()

# Check ALL time_emb_proj layers
for name, module in unet.named_modules():
    if 'time_emb_proj' in name:
        for pname, param in module.named_parameters():
            data = param.data
            has_nan = torch.isnan(data).any().item()
            has_inf = torch.isinf(data).any().item()
            absmax = data.float().abs().max().item()
            print(f'{name}.{pname}: dtype={data.dtype}, shape={data.shape}, absmax={absmax:.1f}, nan={has_nan}, inf={has_inf}')

# Check what happens with float32 projection
r = unet.down_blocks[0].resnets[0]
print(f'\ntime_emb_proj weight: dtype={r.time_emb_proj.weight.dtype}')
print(f'time_emb_proj bias: dtype={r.time_emb_proj.bias.dtype}')

# Test with float32
emb_test = torch.randn(2, 1280, device=dev, dtype=torch.float32) * 5  # similar to real values
with torch.no_grad():
    # fp16
    out16 = r.time_emb_proj(emb_test.half())
    print(f'\nfp16 output: nan={torch.isnan(out16).any()}, range=[{out16.float().min():.3f},{out16.float().max():.3f}]')
    
    # fp32
    orig_w = r.time_emb_proj.weight.data.clone()
    orig_b = r.time_emb_proj.bias.data.clone()
    r.time_emb_proj.weight.data = orig_w.float()
    r.time_emb_proj.bias.data = orig_b.float()
    out32 = r.time_emb_proj(emb_test)
    print(f'fp32 output: nan={torch.isnan(out32).any()}, range=[{out32.float().min():.3f},{out32.float().max():.3f}]')
    r.time_emb_proj.weight.data = orig_w
    r.time_emb_proj.bias.data = orig_b
