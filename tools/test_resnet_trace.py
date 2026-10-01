"""Minimal ResNet trace: skip unet_encoder, use random ref features."""
import os, sys, torch, time
sys.path.insert(0, r'D:\ai_projects\ComfyUI')
sys.path.insert(0, r'D:\ai_projects\ComfyUI\custom_nodes\ComfyUI-IDM-VTON')

# GroupNorm fix (with weight/bias)
_orig_gn_fwd = torch.nn.GroupNorm.forward
def _safe_gn_fwd(self, x):
    x_f32 = x.float()
    w = self.weight.float() if self.weight is not None else None
    b = self.bias.float() if self.bias is not None else None
    return torch.nn.functional.group_norm(x_f32, self.num_groups, w, b, self.eps).to(x.dtype)
torch.nn.GroupNorm.forward = _safe_gn_fwd

from diffusers import AutoencoderKL
from src.idm_vton.unet_hacked_tryon import UNet2DConditionModel
import folder_paths

WP = os.path.join(folder_paths.models_dir, 'IDM-VTON')
dt = torch.float16
dev = 'cuda'

print('Loading unet...')
unet = UNet2DConditionModel.from_pretrained(WP, subfolder='unet', torch_dtype=dt).to(dev).eval()
print(f'GPU: {torch.cuda.memory_allocated()/1024**3:.1f}GB')

w, h = 384, 512
batch = 2  # CFG

# Random inputs (skip VAE etc.)
sample = torch.randn(batch, 13, h//8, w//8, device=dev, dtype=dt)
t = torch.tensor([801, 801], device=dev)
prompt_embeds = torch.randn(batch, 77, 2048, device=dev, dtype=dt)
add_time_ids = torch.tensor([[h, w, 0, 0, h, w]], device=dev, dtype=dt).repeat(batch, 1)
add_text_embeds = torch.randn(batch, 1280, device=dev, dtype=dt)

# Random ref features (70 features matching expected shapes)
ref_features = []
# 4 x [1, 768, 640]
for _ in range(4):
    ref_features.append(torch.randn(1, 768, 640, device=dev, dtype=dt))
# 61 x [1, 192, 1280]
for _ in range(61):
    ref_features.append(torch.randn(1, 192, 1280, device=dev, dtype=dt))
# 5 x [1, 768, 640]
for _ in range(5):
    ref_features.append(torch.randn(1, 768, 640, device=dev, dtype=dt))

# CFG: duplicate
ref_cfg = [torch.cat([torch.zeros_like(d), d]) for d in ref_features]

print(f'\n--- Manual trace (no pipeline, just UNet forward internals) ---')
with torch.no_grad():
    # Timestep embedding
    t_emb = unet.time_proj(t)
    print(f'time_proj: range=[{t_emb.float().min():.6f},{t_emb.float().max():.6f}], nan={torch.isnan(t_emb).any()}')
    t_emb = t_emb.to(dt)
    
    emb = unet.time_embedding(t_emb, None)
    print(f'time_embedding: range=[{emb.float().min():.3f},{emb.float().max():.3f}], nan={torch.isnan(emb).any()}')
    
    # conv_in
    hidden = unet.conv_in(sample)
    print(f'conv_in: range=[{hidden.float().min():.3f},{hidden.float().max():.3f}], nan={torch.isnan(hidden).any()}')
    
    # First resnet
    r = unet.down_blocks[0].resnets[0]
    x = hidden
    print(f'\nFirst ResnetBlock2D:')
    
    # norm1
    h = r.norm1(x)
    print(f'  norm1: range=[{h.float().min():.3f},{h.float().max():.3f}], nan={torch.isnan(h).any()}')
    
    # silu
    h = torch.nn.functional.silu(h)
    print(f'  silu1: range=[{h.float().min():.3f},{h.float().max():.3f}], nan={torch.isnan(h).any()}')
    
    # conv1
    h = r.conv1(h)
    print(f'  conv1: range=[{h.float().min():.3f},{h.float().max():.3f}], nan={torch.isnan(h).any()}')
    
    # time_emb_proj
    temb_silu = torch.nn.functional.silu(emb)
    print(f'  temb_silu: range=[{temb_silu.float().min():.3f},{temb_silu.float().max():.3f}], nan={torch.isnan(temb_silu).any()}')
    t_proj = r.time_emb_proj(temb_silu)
    print(f'  time_emb_proj: range=[{t_proj.float().min():.3f},{t_proj.float().max():.3f}], nan={torch.isnan(t_proj).any()}')
    
    # temb add
    h = h + t_proj[:, :, None, None]
    print(f'  temb_add: range=[{h.float().min():.3f},{h.float().max():.3f}], nan={torch.isnan(h).any()}')
    
    # norm2
    h = r.norm2(h)
    print(f'  norm2: range=[{h.float().min():.3f},{h.float().max():.3f}], nan={torch.isnan(h).any()}')
    
    # silu2
    h = torch.nn.functional.silu(h)
    print(f'  silu2: range=[{h.float().min():.3f},{h.float().max():.3f}], nan={torch.isnan(h).any()}')
    
    # conv2
    h = r.conv2(h)
    print(f'  conv2: range=[{h.float().min():.3f},{h.float().max():.3f}], nan={torch.isnan(h).any()}')
    
    # Shortcut / output
    if r.conv_shortcut is not None:
        x = r.conv_shortcut(x)
    out = h + x
    print(f'  output: range=[{out.float().min():.3f},{out.float().max():.3f}], nan={torch.isnan(out).any()}')
    
    if not torch.isnan(out).any():
        print('\nFirst ResNet: CLEAN. Checking first attention...')
        hidden = out
        
        # The first attention block
        attn = unet.down_blocks[0].attentions[0]
        print(f'  attn type: {attn.__class__.__name__}')
        
        # encoder_hidden_states
        enc_hs = prompt_embeds
        
        # Run through block forward
        sample_block, res_samples, curr_idx = unet.down_blocks[0](
            hidden_states=hidden,
            temb=emb,
            encoder_hidden_states=enc_hs,
            attention_mask=None,
            cross_attention_kwargs={},
            encoder_attention_mask=None,
            garment_features=ref_cfg,
            curr_garment_feat_idx=0,
        )
        print(f'  down_block output: nan={torch.isnan(sample_block).any()}, range=[{sample_block.float().min():.3f},{sample_block.float().max():.3f}]')
    else:
        print('\nFirst ResNet: NaN detected!')
