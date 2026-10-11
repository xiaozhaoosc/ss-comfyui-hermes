
from PIL import Image
import numpy as np
import json
import os

image_paths = [
    'd:/ai_projects/ComfyUI/output/test_idm_vton_v3_20260814_00001_.png',
    'd:/ai_projects/ComfyUI/output/test_idm_vton_pose_v3_20260814_00001_.png',
    'd:/ai_projects/ComfyUI/output/test_idm_vton_mask_v3_20260814_00001_.png',
    'd:/ai_projects/ComfyUI/output/mimicmotion_test_short_v2_00001.png',
    'd:/ai_projects/ComfyUI/output/tryon_result_00005_.png',
    'd:/ai_projects/ComfyUI/output/test_faceswap_v2_20260814.png',
    'd:/ai_projects/ComfyUI/input/pics/test_frame_001.png',
    'd:/ai_projects/ComfyUI/input/todo/face/ken4.png'
]

results = []

for path in image_paths:
    try:
        img = Image.open(path)
        img_array = np.array(img)
        
        info = {
            'name': os.path.basename(path),
            'mode': img.mode,
            'size': img.size,
            'bands': img.getbands(),
        }
        
        h, w = img_array.shape[:2]
        num_ch = 3 if len(img_array.shape) == 3 else 1
        
        if num_ch >= 3:
            avg_r = int(np.mean(img_array[:,:,0]))
            avg_g = int(np.mean(img_array[:,:,1]))
            avg_b = int(np.mean(img_array[:,:,2]))
            info['avg_rgb'] = [avg_r, avg_g, avg_b]
            info['brightness'] = round((avg_r * 299 + avg_g * 587 + avg_b * 114) / 1000, 1)
            info['std_rgb'] = [
                round(float(np.std(img_array[:,:,0])), 1),
                round(float(np.std(img_array[:,:,1])), 1),
                round(float(np.std(img_array[:,:,2])), 1)
            ]
            grid_colors = []
            rows, cols = 3, 3
            for r in range(rows):
                row_colors = []
                for c in range(cols):
                    r0, r1 = r * h // rows, (r + 1) * h // rows
                    c0, c1 = c * w // cols, (c + 1) * w // cols
                    block = img_array[r0:r1, c0:c1, :3]
                    row_colors.append([
                        int(np.mean(block[:,:,0])),
                        int(np.mean(block[:,:,1])),
                        int(np.mean(block[:,:,2]))
                    ])
                grid_colors.append(row_colors)
            info['grid_3x3_rgb'] = grid_colors
            
            top_half = img_array[:h//2, :, :3]
            bottom_half = img_array[h//2:, :, :3]
            top_bright = round((np.mean(top_half[:,:,0])*299 + np.mean(top_half[:,:,1])*587 + np.mean(top_half[:,:,2])*114)/1000, 1)
            bot_bright = round((np.mean(bottom_half[:,:,0])*299 + np.mean(bottom_half[:,:,1])*587 + np.mean(bottom_half[:,:,2])*114)/1000, 1)
            info['top_brightness'] = top_bright
            info['bottom_brightness'] = bot_bright
            info['vertical_diff'] = round(abs(top_bright - bot_bright), 1)
            
            face_region = img_array[h//8:h//3, w//4:3*w//4, :3]
            info['face_region_rgb'] = [
                int(np.mean(face_region[:,:,0])),
                int(np.mean(face_region[:,:,1])),
                int(np.mean(face_region[:,:,2]))
            ]
            
            gray = np.mean(img_array[:,:,:3], axis=2)
            info['dark_ratio_50'] = round(float(np.sum(gray < 50) / gray.size * 100), 1)
            info['white_ratio_205'] = round(float(np.sum(gray > 205) / gray.size * 100), 1)
            info['gray_std'] = round(float(np.std(gray)), 1)
            info['monochrome'] = bool(
                np.allclose(np.std(img_array[:,:,0] - img_array[:,:,1]), 0, atol=5) and
                np.allclose(np.std(img_array[:,:,1] - img_array[:,:,2]), 0, atol=5)
            )
        
        sample = img_array[::8, ::8].reshape(-1, num_ch)
        if num_ch >= 3:
            sample = sample[:, :3]
        info['unique_colors_sampled'] = len(np.unique(sample, axis=0))
        
        results.append(info)
        img.close()
    except Exception as e:
        results.append({'name': os.path.basename(path), 'error': str(e)})

print(json.dumps(results, indent=2, ensure_ascii=False))
