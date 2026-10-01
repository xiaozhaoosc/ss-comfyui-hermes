"""
Flux.1 Dev + PuLID 商业换脸驱动脚本 (SDK 版)
基于 ComfyClient SDK 实现，代码量大幅精简。
"""
import sys
import os
import logging
import argparse

# 将 projects 目录加入 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdk.comfy_client import ComfyClient

# ─── 日志配置 ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "logs", "run.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("flux_pulid")

# ─── 默认参数 ────────────────────────────────────────────────
WORKFLOW_PATH = os.path.join(os.path.dirname(__file__), "flux_pulid_workflow_api.json")
DEFAULT_PROMPT = "A high-end cinematic photo of a professional model, photorealistic, 8k resolution, studio lighting"


def run_single(
    face_path: str,
    body_path: str,
    prompt: str = DEFAULT_PROMPT,
    weight: float = 0.85,
    guidance: float = 3.5,
    steps: int = 20,
    denoise: float = 0.35,
    output_dir: str = "output",
):
    """执行单次换脸任务"""
    client = ComfyClient()

    # 健康检查
    if not client.health_check():
        logger.error("ComfyUI 服务未启动！请先运行 ComfyUI。")
        sys.exit(1)

    # 通过 Title 锚定覆盖参数
    overrides = {
        "SOURCE_FACE_LOADER": {"image": face_path},
        "TARGET_BODY_LOADER": {"image": body_path},
        "PULID_FLUX_APPLIER": {"weight": weight},
        "正向提示词输入": {"text": prompt},
        "Flux 引导控制器": {"guidance": guidance},
        "时间步调度器": {"steps": steps, "denoise": denoise},
        "随机噪声源": {"noise_seed": int.from_bytes(os.urandom(4), "big")},
    }

    logger.info(f"启动 Flux PuLID 换脸任务")
    logger.info(f"  源脸: {face_path}")
    logger.info(f"  身躯: {body_path}")
    logger.info(f"  权重: {weight} | 引导: {guidance} | 步数: {steps} | 降噪: {denoise}")

    results = client.run_workflow(
        workflow_path=WORKFLOW_PATH,
        overrides=overrides,
        save_dir=output_dir,
        timeout=300,
    )

    if results:
        logger.info(f"换脸完成! 产物: {results}")
    else:
        logger.error("换脸任务失败，未获取到任何输出。")

    return results


def run_sweep(
    face_path: str,
    body_path: str,
    output_dir: str = "output/sweep",
):
    """参数扫描模式：遍历多组 weight × guidance 参数组合"""
    weights = [0.7, 0.8, 0.85, 0.9]
    guidances = [3.0, 3.5, 4.0]

    logger.info(f"启动参数扫描模式: {len(weights)} × {len(guidances)} = {len(weights) * len(guidances)} 组")

    for w in weights:
        for g in guidances:
            sub_dir = os.path.join(output_dir, f"w{w}_g{g}")
            logger.info(f"\n{'='*50}\n  扫描: weight={w}, guidance={g}\n{'='*50}")
            try:
                run_single(
                    face_path=face_path,
                    body_path=body_path,
                    weight=w,
                    guidance=g,
                    output_dir=sub_dir,
                )
            except Exception as e:
                logger.error(f"扫描任务 w={w} g={g} 失败: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flux.1 Dev + PuLID 商业换脸驱动")
    parser.add_argument("--face", required=True, help="源人脸图片路径")
    parser.add_argument("--body", required=True, help="目标身躯模特图片路径")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="正向提示词")
    parser.add_argument("--weight", type=float, default=0.85, help="PuLID 人脸相似度权重")
    parser.add_argument("--guidance", type=float, default=3.5, help="Flux 引导度")
    parser.add_argument("--steps", type=int, default=20, help="采样步数")
    parser.add_argument("--denoise", type=float, default=0.35, help="降噪幅度")
    parser.add_argument("--output", default="output", help="输出目录")
    parser.add_argument("--sweep", action="store_true", help="启用参数扫描模式")

    args = parser.parse_args()

    if args.sweep:
        run_sweep(args.face, args.body, args.output)
    else:
        run_single(
            face_path=args.face,
            body_path=args.body,
            prompt=args.prompt,
            weight=args.weight,
            guidance=args.guidance,
            steps=args.steps,
            denoise=args.denoise,
            output_dir=args.output,
        )
