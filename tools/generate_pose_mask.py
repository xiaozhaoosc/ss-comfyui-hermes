"""Generate pose and mask for IDM-VTON using local models"""
import os, sys, torch, time
import numpy as np
from PIL import Image
import cv2

COMFY_ROOT = r'D:\ai_projects\ComfyUI'
sys.path.insert(0, COMFY_ROOT)

# === Generate pose using OpenPose (IDM-VTON bundled model) ===
def generate_pose_openpose(person_img_path, output_path):
    """Use IDM-VTON's bundled OpenPose model to generate pose."""
    # Use the comfyui_controlnet_aux DWPose with TorchScript
    ckpts_dir = os.path.join(COMFY_ROOT, 'custom_nodes', 'comfyui_controlnet_aux', 'ckpts')
    
    # Load person image
    img = Image.open(person_img_path).convert('RGB')
    img_np = np.array(img)
    
    print(f'  Input image: {img_np.shape}')
    
    # Use OpenCV DNN for pose estimation as a simpler alternative
    # Actually, let's use the TorchScript models directly
    yolox_path = os.path.join(ckpts_dir, 'hr16', 'yolox-onnx', 'yolox_l.torchscript.pt')
    dwpose_path = os.path.join(ckpts_dir, 'hr16', 'DWPose-TorchScript-BatchSize5', 'dw-ll_ucoco_384_bs5.torchscript.pt')
    
    print(f'  Loading YOLOX: {yolox_path}')
    print(f'  Loading DWPose: {dwpose_path}')
    
    # Load models
    yolox = torch.jit.load(yolox_path, map_location='cuda')
    dwpose = torch.jit.load(dwpose_path, map_location='cuda')
    
    # Preprocess image for YOLOX
    h, w = img_np.shape[:2]
    # Resize to 640 for YOLOX
    scale = 640 / max(h, w)
    new_h, new_w = int(h * scale), int(w * scale)
    img_resized = cv2.resize(img_np, (new_w, new_h))
    
    # Pad to 640x640
    padded = np.zeros((640, 640, 3), dtype=np.uint8)
    padded[:new_h, :new_w] = img_resized
    
    # Normalize
    input_tensor = torch.from_numpy(padded).float().permute(2, 0, 1).unsqueeze(0).cuda() / 255.0
    
    # Run YOLOX for person detection
    with torch.no_grad():
        detections = yolox(input_tensor)
    
    print(f'  Detections shape: {detections.shape if hasattr(detections, "shape") else type(detections)}')
    
    # For now, use the whole image as the person region
    # This is a simplified approach - proper implementation would parse detections
    
    return None

# === Generate mask using human parsing (ONNX) ===
def generate_mask_parsing(person_img_path, output_path):
    """Use IDM-VTON's human parsing ONNX models to generate mask."""
    import onnxruntime as ort
    
    parsing_path = os.path.join(COMFY_ROOT, 'models', 'IDM-VTON', 'humanparsing', 'parsing_atr.onnx')
    
    print(f'  Loading parsing model: {parsing_path}')
    session = ort.InferenceSession(parsing_path, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    
    # Load and preprocess image
    img = Image.open(person_img_path).convert('RGB')
    orig_w, orig_h = img.size
    
    # Resize to model input size (512x512 for ATR)
    input_size = (512, 512)
    img_resized = img.resize(input_size, Image.BILINEAR)
    
    # Normalize
    img_np = np.array(img_resized).astype(np.float32)
    img_np = img_np / 255.0
    img_np = (img_np - np.array([0.406, 0.456, 0.485])) / np.array([0.225, 0.224, 0.229])
    img_np = img_np.transpose(2, 0, 1)[np.newaxis].astype(np.float32)
    
    # Run inference
    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: img_np})
    parsing = output[0][0]  # Shape: (H, W) with class labels
    
    print(f'  Parsing shape: {parsing.shape}')
    print(f'  Unique labels: {np.unique(parsing)}')
    
    # ATR labels: 0=background, 1=hat, 2=hair, 3=sunglasses, 4=upper-clothes, 5=skirt, 6=pants, 7=dress, 8=belt, 9=left-shoe, 10=right-shoe, 11=face, 12=left-leg, 13=right-leg, 14=left-arm, 15=right-arm, 16=bag, 17=scarf
    # Mask = upper-clothes(4) + dress(7) + belt(8) — the clothing area to replace
    clothing_labels = [4, 7, 8]  # upper-clothes, dress, belt
    mask = np.isin(parsing, clothing_labels).astype(np.uint8) * 255
    
    # Resize back to original
    mask_pil = Image.fromarray(mask).resize((orig_w, orig_h), Image.NEAREST)
    mask_pil.save(output_path)
    print(f'  Saved mask: {output_path}')
    
    # Also save the full parsing for debugging
    parsing_color = np.zeros((*parsing.shape, 3), dtype=np.uint8)
    colors = [
        [0,0,0], [204,0,0], [76,153,0], [204,204,0], [51,51,255],
        [204,0,204], [0,255,255], [255,204,204], [102,51,0], [255,0,0],
        [102,204,0], [255,255,0], [0,0,153], [0,0,204], [255,51,153],
        [0,204,204], [0,51,0], [255,153,51]
    ]
    for i, color in enumerate(colors):
        parsing_color[parsing == i] = color
    
    Image.fromarray(parsing_color).save(output_path.replace('.png', '_parsing.png'))
    print(f'  Saved parsing: {output_path.replace(".png", "_parsing.png")}')
    
    return mask_pil


if __name__ == '__main__':
    person_path = 'input/todo/idm_vton_test/person.png'
    
    print('=== Generating mask via human parsing ===')
    os.makedirs('input/todo/vton_test', exist_ok=True)
    generate_mask_parsing(person_path, 'input/todo/vton_test/mask_auto.png')
    
    print('\n=== Generating pose ===')
    # For pose, let's use the DWPose via comfyui_controlnet_aux directly
    # This is complex - let me use a simpler approach with OpenPose
    print('  Skipping pose generation for now - will use comfyui_controlnet_aux DWPose')
    print('  For now, creating a pose from the person image using edge detection')
    
    img = cv2.imread(person_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
    cv2.imwrite('input/todo/vton_test/pose_edge.png', edges_colored)
    print(f'  Saved edge-based pose: input/todo/vton_test/pose_edge.png')
