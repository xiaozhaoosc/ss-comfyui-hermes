"""Face-Protected Clothing Mask Generator for IDM-VTON

Uses the existing parsing_atr.onnx human parsing model to generate
a clothing mask that explicitly excludes face, hair, and sunglasses
regions, preventing the IDM-VTON inpainting from corrupting facial features.

ATR Labels:
  0=background, 1=hat, 2=hair, 3=sunglasses, 4=upper-clothes,
  5=skirt, 6=pants, 7=dress, 8=belt, 9=left-shoe, 10=right-shoe,
  11=face, 12=left-leg, 13=right-leg, 14=left-arm, 15=right-arm,
  16=bag, 17=scarf
"""
import os
import numpy as np
import torch
from PIL import Image
import folder_paths


class FaceProtectMask:
    """Generate a clothing mask with face protection for IDM-VTON."""

    _session = None  # Class-level cache for ONNX session

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "clothing_labels": ("STRING", {
                    "default": "4,7,8",
                    "tooltip": "Clothing labels to mask (ATR): 4=upper-clothes, 5=skirt, 6=pants, 7=dress, 8=belt"
                }),
                "protect_labels": ("STRING", {
                    "default": "2,3,11",
                    "tooltip": "Face/body labels to protect: 1=hat, 2=hair, 3=sunglasses, 11=face"
                }),
                "protect_expand": ("INT", {
                    "default": 10,
                    "min": 0,
                    "max": 50,
                    "tooltip": "Expand protection zone by N pixels (safety margin around face)"
                }),
                "feather": ("INT", {
                    "default": 5,
                    "min": 0,
                    "max": 30,
                    "tooltip": "Feather mask edges by N pixels for smoother blending"
                }),
            }
        }

    RETURN_TYPES = ("MASK", "IMAGE")
    RETURN_NAMES = ("mask", "parsing_preview")
    FUNCTION = "generate"
    CATEGORY = "ComfyUI-IDM-VTON"

    def _get_session(self):
        if FaceProtectMask._session is None:
            import onnxruntime as ort
            parsing_path = os.path.join(
                folder_paths.models_dir, "IDM-VTON", "humanparsing", "parsing_atr.onnx"
            )
            if not os.path.exists(parsing_path):
                raise FileNotFoundError(f"parsing_atr.onnx not found at {parsing_path}")
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            FaceProtectMask._session = ort.InferenceSession(parsing_path, providers=providers)
        return FaceProtectMask._session

    def _run_parsing(self, image_np):
        """Run human parsing on image, returns label map (H, W)."""
        session = self._get_session()
        h, w = image_np.shape[:2]

        # Preprocess: resize to 512x512, normalize
        img_pil = Image.fromarray(image_np).resize((512, 512), Image.BILINEAR)
        img_np_512 = np.array(img_pil).astype(np.float32)
        img_np_512 = img_np_512 / 255.0
        img_np_512 = (img_np_512 - np.array([0.406, 0.456, 0.485])) / np.array([0.225, 0.224, 0.229])
        img_np_512 = img_np_512.transpose(2, 0, 1)[np.newaxis].astype(np.float32)

        # Run inference
        input_name = session.get_inputs()[0].name
        output = session.run(None, {input_name: img_np_512})
        # Output shape: (1, 18, 128, 128) — 18-class probability map at 128x128
        prob_map = output[0][0]  # (18, 128, 128)
        parsing_128 = np.argmax(prob_map, axis=0).astype(np.uint8)  # (128, 128)

        # Resize from 128x128 to original resolution
        parsing_pil = Image.fromarray(parsing_128)
        parsing_full = np.array(parsing_pil.resize((w, h), Image.NEAREST))
        return parsing_full

    def _expand_mask(self, mask, pixels):
        """Expand white region of mask by N pixels (dilation)."""
        if pixels <= 0:
            return mask
        import cv2
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (pixels * 2 + 1, pixels * 2 + 1))
        return cv2.dilate(mask, kernel, iterations=1)

    def _feather_mask(self, mask, pixels):
        """Feather edges of mask for smoother blending."""
        if pixels <= 0:
            return mask
        import cv2
        return cv2.GaussianBlur(mask, (pixels * 2 + 1, pixels * 2 + 1), 0)

    def generate(self, image, clothing_labels, protect_labels, protect_expand, feather):
        import cv2

        # Convert ComfyUI IMAGE (BHWC float32 0-1) to numpy
        img_np = (image.squeeze(0).cpu().numpy() * 255).astype(np.uint8)

        # Run parsing
        parsing = self._run_parsing(img_np)

        # Parse label lists
        cloth_ids = [int(x.strip()) for x in clothing_labels.split(",") if x.strip()]
        protect_ids = [int(x.strip()) for x in protect_labels.split(",") if x.strip()]

        # Generate clothing mask (white = area to replace)
        cloth_mask = np.isin(parsing, cloth_ids).astype(np.uint8) * 255

        # Generate protection mask (white = area to protect)
        protect_mask = np.isin(parsing, protect_ids).astype(np.uint8) * 255

        # Expand protection zone for safety margin
        protect_mask = self._expand_mask(protect_mask, protect_expand)

        # Subtract protection from clothing mask
        result_mask = cv2.bitwise_and(cloth_mask, cv2.bitwise_not(protect_mask))

        # Fill holes in clothing mask (morphological close)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        result_mask = cv2.morphologyEx(result_mask, cv2.MORPH_CLOSE, kernel)

        # Feather edges for smooth blending
        result_mask = self._feather_mask(result_mask, feather)

        # Create parsing preview (colored visualization)
        h, w = parsing.shape
        preview = np.zeros((h, w, 3), dtype=np.uint8)
        colors = [
            [0,0,0], [204,0,0], [76,153,0], [204,204,0], [51,51,255],
            [204,0,204], [0,255,255], [255,204,204], [102,51,0], [255,0,0],
            [102,204,0], [255,255,0], [0,0,153], [0,0,204], [255,51,153],
            [0,204,204], [0,51,0], [255,153,51]
        ]
        for i, color in enumerate(colors):
            preview[parsing == i] = color

        # Overlay protection zones in red tint
        protect_vis = protect_mask > 0
        preview[protect_vis] = (preview[protect_vis] * 0.5 + np.array([255, 0, 0]) * 0.5).astype(np.uint8)

        # Convert to ComfyUI format
        mask_tensor = torch.from_numpy(result_mask.astype(np.float32) / 255.0).unsqueeze(0)
        preview_tensor = torch.from_numpy(preview.astype(np.float32) / 255.0).unsqueeze(0)

        return (mask_tensor, preview_tensor)
