import urllib.request
import json
import time
import sys

prompt = {
  "1": {
    "class_type": "UNETLoader",
    "inputs": {
      "unet_name": "flux1-dev-fp8.safetensors",
      "weight_dtype": "fp8_e4m3fn"
    }
  },
  "2": {
    "class_type": "DualCLIPLoader",
    "inputs": {
      "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
      "clip_name2": "clip_l.safetensors",
      "type": "flux"
    }
  },
  "3": {
    "class_type": "VAELoader",
    "inputs": {
      "vae_name": "flux-vae-bf16.safetensors"
    }
  },
  "20": {
    "class_type": "LoraLoader",
    "inputs": {
      "lora_name": "hinaFluxDevAsianMix_v12.safetensors",
      "strength_model": 0.85,
      "strength_clip": 0.85,
      "model": ["1", 0],
      "clip": ["2", 0]
    }
  },
  "4": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "Full body mirror selfie of a stunning Korean drama lead actress, fair luminous porcelain skin, silky straight dark brown hair. Standing tall in front of a floor-to-ceiling mirror with endless slender long legs. Wearing an unbuttoned crisp bright cobalt azure blue linen boyfriend shirt over a white ribbed crop tank top, high-waisted tailored khaki chino shorts cinched at the high waist, bare legs, nude pointed kitten heels. Holding a sleek modern smartphone in both hands taking a candid reflection photo. Elegant bright modern apartment interior, quiet luxury aesthetic, 8k resolution, cinematic soft interior lighting, sharp focus on slender silhouette.",
      "clip": ["20", 1]
    }
  },
  "5": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "short legs, thick thighs, dwarf proportions, stubby legs, disproportionate body, extra limbs, bad hands, deformed feet, blurry, low quality, oversaturated",
      "clip": ["20", 1]
    }
  },
  "10": {
    "class_type": "FluxGuidance",
    "inputs": {
      "guidance": 3.5,
      "conditioning": ["4", 0]
    }
  },
  "11": {
    "class_type": "FluxGuidance",
    "inputs": {
      "guidance": 1.0,
      "conditioning": ["5", 0]
    }
  },
  "30": {
    "class_type": "ControlNetLoader",
    "inputs": {
      "control_net_name": "flux_controlnet_union_pro_2.0.safetensors"
    }
  },
  "31": {
    "class_type": "SetUnionControlNetType",
    "inputs": {
      "control_net": ["30", 0],
      "type": "openpose"
    }
  },
  "32": {
    "class_type": "LoadImage",
    "inputs": {
      "image": "pose_stretched_supermodel.png"
    }
  },
  "33": {
    "class_type": "ControlNetApplyAdvanced",
    "inputs": {
      "positive": ["10", 0],
      "negative": ["11", 0],
      "control_net": ["31", 0],
      "image": ["32", 0],
      "strength": 0.80,
      "start_percent": 0.0,
      "end_percent": 0.85,
      "vae": ["3", 0]
    }
  },
  "6": {
    "class_type": "EmptySD3LatentImage",
    "inputs": {
      "width": 768,
      "height": 1280,
      "batch_size": 1
    }
  },
  "7": {
    "class_type": "KSampler",
    "inputs": {
      "seed": 928302,
      "steps": 20,
      "cfg": 1.0,
      "sampler_name": "euler",
      "scheduler": "simple",
      "denoise": 1.0,
      "model": ["20", 0],
      "positive": ["33", 0],
      "negative": ["33", 1],
      "latent_image": ["6", 0]
    }
  },
  "8": {
    "class_type": "VAEDecode",
    "inputs": {
      "samples": ["7", 0],
      "vae": ["3", 0]
    }
  },
  "9": {
    "class_type": "SaveImage",
    "inputs": {
      "filename_prefix": "2026-09-28/scheme3_controlnet_supermodel_02",
      "images": ["8", 0]
    }
  }
}

req = urllib.request.Request(
    'http://127.0.0.1:8188/prompt',
    data=json.dumps({'prompt': prompt}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    res = urllib.request.urlopen(req)
    data = json.loads(res.read())
    prompt_id = data.get('prompt_id')
    print(f"Task queued successfully! Prompt ID: {prompt_id}")
    
    start_time = time.time()
    while True:
        time.sleep(3)
        try:
            h_req = urllib.request.urlopen(f'http://127.0.0.1:8188/history/{prompt_id}')
            history = json.loads(h_req.read())
            if prompt_id in history:
                elapsed = time.time() - start_time
                outputs = history[prompt_id].get('outputs', {})
                print(f"Generation completed in {elapsed:.1f}s!")
                print("Outputs:", json.dumps(outputs, indent=2))
                break
        except Exception as poll_err:
            print("Poll error:", poll_err)

except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
