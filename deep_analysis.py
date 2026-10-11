
from PIL import Image
import numpy as np
import json
import os

def load_img_rgb(path):
    img = Image.open(path)
    if img.mode == 'RGBA':
        bg = Image.new('RGB', img.size, (255,255,255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    return img

def resize_to_match(img, target_size):
    return img.resize(target_size, Image.LANCZOS)

def img_to_array(img):
    return np.array(img).astype(np.float32)

def compute_ssim_approx(a, b):
    # 简化结构相似度 (0-1)
    C1 = (0.01 * 255)**2
    C2 = (0.03 * 255)**2
    mu_a = np.mean(a)
    mu_b = np.mean(b)
    sigma_a_sq = np.var(a)
    sigma_b_sq = np.var(b)
    sigma_ab = np.mean((a - mu_a) * (b - mu_b))
    ssim = ((2*mu_a*mu_b + C1) * (2*sigma_ab + C2)) / ((mu_a**2 + mu_b**2 + C1) * (sigma_a_sq + sigma_b_sq + C2))
    return float(ssim)

def psnr(a, b):
    mse = np.mean((a - b)**2)
    if mse == 0:
        return 100.0
    return float(20 * np.log10(255.0 / np.sqrt(mse)))

def pixel_match_ratio(a, b, threshold=15):
    # 颜色差小于阈值的像素比例
    diff = np.abs(a - b)
    per_pixel_max = np.max(diff, axis=2)
    match = np.sum(per_pixel_max < threshold) / per_pixel_max.size
    return float(match * 100)

def region_analysis(arr, name):
    h, w = arr.shape[:2]
    out = {}
    # 4个区域: 头(上1/4), 躯干(中2/4), 腿(下1/4)
    regions = {
        'head_top': (0, h//4, w//4, 3*w//4),
        'torso_mid': (h//4, 3*h//4, w//6, 5*w//6),
        'legs_bot': (3*h//4, h, w//5, 4*w//5),
        'bg_left': (0, h, 0, w//6),
        'bg_right': (0, h, 5*w//6, w),
    }
    for rname, (r0, r1, c0, c1) in regions.items():
        blk = arr[r0:r1, c0:c1]
        out[rname + '_avg'] = [int(np.mean(blk[:,:,i])) for i in range(3)]
        out[rname + '_bright'] = round(np.mean(blk[:,:,0])*0.299 + np.mean(blk[:,:,1])*0.587 + np.mean(blk[:,:,2])*0.114, 1)
    return out

def color_hist_summary(arr, bins=8):
    # 每个通道的8个bin的分布百分比
    out = {}
    for ch_i, ch_name in enumerate(['R','G','B']):
        hist, _ = np.histogram(arr[:,:,ch_i].flatten(), bins=bins, range=(0,256))
        pct = (hist / hist.size * 100).round(1).tolist()
        out[f'hist_{ch_name}'] = pct
    # 冷暖色调比例: 红>蓝偏暖, 蓝>红偏冷
    warm = np.sum(arr[:,:,0] > arr[:,:,2]) / arr[:,:,0].size * 100
    cool = 100 - warm
    out['warm_pct'] = round(float(warm), 1)
    out['cool_pct'] = round(float(cool), 1)
    # 肤色比例估计: R in 140-240, G in 90-190, B in 70-160, R>G>B
    r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
    skin_mask = (r>140)&(r<240) & (g>90)&(g<190) & (b>70)&(b<160) & (r>g) & (g>b)
    out['skin_est_pct'] = round(float(np.sum(skin_mask)/skin_mask.size*100), 1)
    # 蓝色区域(深蓝裤子)估计
    blue_mask = (b>r+15) & (b>g+15) & (b>80)
    out['blue_region_pct'] = round(float(np.sum(blue_mask)/blue_mask.size*100), 1)
    # 高亮白/浅区域(上衣等)
    gray = np.mean(arr, axis=2)
    white_mask = (gray>200) & (np.std(arr, axis=2)<25)
    out['light_white_pct'] = round(float(np.sum(white_mask)/white_mask.size*100), 1)
    return out

# === 加载所有图片 ===
paths = {
    'vton_out': 'd:/ai_projects/ComfyUI/output/test_idm_vton_v3_20260814_00001_.png',
    'pose': 'd:/ai_projects/ComfyUI/output/test_idm_vton_pose_v3_20260814_00001_.png',
    'mask': 'd:/ai_projects/ComfyUI/output/test_idm_vton_mask_v3_20260814_00001_.png',
    'mimic_out': 'd:/ai_projects/ComfyUI/output/mimicmotion_test_short_v2_00001.png',
    'tryon_out': 'd:/ai_projects/ComfyUI/output/tryon_result_00005_.png',
    'faceswap_out': 'd:/ai_projects/ComfyUI/output/test_faceswap_v2_20260814.png',
    'vton_input': 'd:/ai_projects/ComfyUI/input/pics/test_frame_001.png',
    'ken_ref': 'd:/ai_projects/ComfyUI/input/todo/face/ken4.png',
}

imgs = {k: load_img_rgb(v) for k,v in paths.items()}
arrs = {k: img_to_array(v) for k,v in imgs.items()}

result = {'per_image': {}, 'comparisons': {}}

# === 每张图的详细分析 ===
for k, arr in arrs.items():
    info = {}
    info['shape'] = list(arr.shape[:2])
    info.update(region_analysis(arr, k))
    info.update(color_hist_summary(arr))
    result['per_image'][k] = info
    print(f"Analyzed {k}")

# === 差异对比 ===
def compare(key_a, key_b, label):
    a = arrs[key_a]
    b = arrs[key_b]
    ta = imgs[key_a]
    tb = imgs[key_b]
    # 对齐尺寸
    if ta.size != tb.size:
        target = ta.size
        tb_r = resize_to_match(tb, target)
        b = img_to_array(tb_r)
    comp = {
        'label': label,
        'psnr': round(psnr(a, b), 2),
        'ssim_approx': round(compute_ssim_approx(a, b), 4),
        'match_pct_15': round(pixel_match_ratio(a, b, 15), 1),
        'match_pct_30': round(pixel_match_ratio(a, b, 30), 1),
        'avg_abs_diff_rgb': [round(float(np.mean(np.abs(a[:,:,i]-b[:,:,i]))),1) for i in range(3)],
        'max_diff_rgb': [int(np.max(np.abs(a[:,:,i]-b[:,:,i]))) for i in range(3)],
    }
    # 按区域比较 (服装在躯干)
    h, w = a.shape[:2]
    r0, r1 = h//4, 3*h//4
    c0, c1 = w//5, 4*w//5
    torso_a = a[r0:r1, c0:c1]
    torso_b = b[r0:r1, c0:c1]
    comp['torso_ssim'] = round(compute_ssim_approx(torso_a, torso_b), 4)
    comp['torso_match_pct'] = round(pixel_match_ratio(torso_a, torso_b, 20), 1)
    # 面部区域比较
    r0, r1 = h//8, h//3
    c0, c1 = w//4, 3*w//4
    face_a = a[r0:r1, c0:c1]
    face_b = b[r0:r1, c0:c1]
    comp['face_ssim'] = round(compute_ssim_approx(face_a, face_b), 4)
    comp['face_match_pct'] = round(pixel_match_ratio(face_a, face_b, 20), 1)
    result['comparisons'][f'{key_a}_vs_{key_b}'] = comp
    print(f"Compared {label}")

compare('vton_input', 'vton_out', 'IDM输入原图 vs IDM换装结果')
compare('ken_ref', 'mimic_out', 'Ken参考图 vs MimicMotion输出')
compare('ken_ref', 'faceswap_out', 'Ken参考图 vs 换脸换装组合结果')
compare('mimic_out', 'faceswap_out', 'MimicMotion输出 vs 换脸换装组合')
compare('vton_out', 'tryon_out', 'IDM单帧结果 vs 视频逐帧结果05')

# === Mask图分析: mask覆盖的位置和面积 ===
mask_arr = arrs['mask']
gray_mask = np.mean(mask_arr, axis=2)
# 黑色区域 (mask < 128): 这是实际需要换服装的区域
mask_area = np.sum(gray_mask < 128) / gray_mask.size * 100
# 找出mask的边界
y_coords, x_coords = np.where(gray_mask < 128)
if len(y_coords) > 0:
    h, w = gray_mask.shape
    result['mask_analysis'] = {
        'mask_area_pct': round(float(mask_area), 1),
        'bbox_y_ratio': [round(float(y_coords.min()/h),3), round(float(y_coords.max()/h),3)],
        'bbox_x_ratio': [round(float(x_coords.min()/w),3), round(float(x_coords.max()/w),3)],
        'bbox_position': f"y范围: {y_coords.min()}-{y_coords.max()}/{h}, x范围: {x_coords.min()}-{x_coords.max()}/{w}",
        'mask_shape_estimate': '覆盖躯干+下身' if (y_coords.max()-y_coords.min())/h > 0.4 else '仅上半身'
    }

# === Pose图分析 ===
pose_arr = arrs['pose']
# 统计非黑色像素分区颜色
non_black = np.sum(pose_arr, axis=2) > 20
pose_area = np.sum(non_black) / non_black.size * 100
# DensePose分区: 统计不同颜色区域
yp, xp, _ = np.where(non_black[:, :, None])
if len(yp) > 0:
    h, w = non_black.shape
    # 头部: 黄区 (高R+G低B)
    head_mask = non_black & (pose_arr[:,:,0]>120) & (pose_arr[:,:,1]>80) & (pose_arr[:,:,2]<60)
    # 躯干上: 蓝绿
    torso_mask = non_black & (pose_arr[:,:,2]>80) & (pose_arr[:,:,0]<80)
    # 腿: 蓝白亮
    leg_mask = non_black & (pose_arr[:,:,2]>150)
    result['pose_analysis'] = {
        'pose_detected_area_pct': round(float(pose_area),1),
        'head_y_ratio': [round(float(np.min(np.where(head_mask)[0])/h),3) if np.any(head_mask) else None,
                         round(float(np.max(np.where(head_mask)[0])/h),3) if np.any(head_mask) else None],
        'torso_detected': bool(np.any(torso_mask)),
        'legs_detected': bool(np.any(leg_mask)),
        'total_keypoint_area': f"约{round(float(pose_area),1)}%的像素被标注为人体",
        'color_regions': {
            'head_like_pct': round(float(np.sum(head_mask)/non_black.size*100),2),
            'torso_like_pct': round(float(np.sum(torso_mask)/non_black.size*100),2),
            'leg_like_pct': round(float(np.sum(leg_mask)/non_black.size*100),2),
        }
    }

print(json.dumps(result, indent=2, ensure_ascii=False))
