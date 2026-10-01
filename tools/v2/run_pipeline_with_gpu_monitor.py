"""
GPU 利用率监控 + faceswap_tryon_pipeline.py 测试运行器
用法:
  python run_pipeline_with_gpu_monitor.py --mode image --input <人物图> --face <人脸图> --garment <服装图> --output <输出>
  python run_pipeline_with_gpu_monitor.py --mode image --skip-faceswap --input <人物图> --garment <服装图> --output <输出>

会在测试过程中持续采样 GPU 使用率，最后输出统计报告。
"""
import os, sys, time, threading, subprocess, argparse, json
from pathlib import Path

# ========== GPU 监控器 ==========
class GPUMonitor:
    """后台线程持续采样 nvidia-smi"""
    def __init__(self, interval=0.5):
        self.interval = interval
        self.samples = []  # [(timestamp, gpu_util%, mem_util%, mem_used_MiB, mem_total_MiB)]
        self._stop = threading.Event()
        self._thread = None
        self._nvidia_smi = self._find_nvidia_smi()

    @staticmethod
    def _find_nvidia_smi():
        # 在常见路径中查找 nvidia-smi
        candidates = [
            r'C:\Windows\System32\nvidia-smi.exe',
            r'C:\Windows\nvidia-smi.exe',
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        # 退回 PATH 查找
        return 'nvidia-smi'

    def _query(self):
        try:
            out = subprocess.run(
                [self._nvidia_smi,
                 '--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=3
            )
            if out.returncode == 0 and out.stdout.strip():
                # 只有一块 GPU 时取第一行
                line = out.stdout.strip().splitlines()[0]
                parts = [x.strip() for x in line.split(',')]
                gpu_util = float(parts[0])
                mem_util = float(parts[1])
                mem_used = float(parts[2])
                mem_total = float(parts[3])
                return gpu_util, mem_util, mem_used, mem_total
        except Exception as e:
            print(f'[GPU Monitor] query failed: {e}', flush=True)
        return None

    def start(self):
        if self._thread is not None:
            return
        # 先做一次预检
        pre = self._query()
        if pre is None:
            print('[GPU Monitor] WARNING: nvidia-smi 不可用，无法监控 GPU 使用率', flush=True)
            return
        print(f'[GPU Monitor] 开始采样 (interval={self.interval}s, 初始: GPU={pre[0]:.0f}%, '
              f'MEM={pre[2]:.0f}/{pre[3]:.0f} MiB)', flush=True)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            sample = self._query()
            if sample is not None:
                self.samples.append((time.time(), *sample))
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def snapshot(self):
        """返回当前快照（用于实时打印）"""
        if not self.samples:
            return None
        return self.samples[-1]

    def report(self, phase_start_idx=0):
        """生成 GPU 使用统计报告"""
        sub = self.samples[phase_start_idx:]
        if not sub:
            return None
        gpu_utils = [s[1] for s in sub]
        mem_utils = [s[2] for s in sub]
        mem_useds = [s[3] for s in sub]
        mem_totals = [s[4] for s in sub]
        return {
            'samples': len(sub),
            'gpu_util_avg': sum(gpu_utils) / len(gpu_utils),
            'gpu_util_max': max(gpu_utils),
            'gpu_util_min': min(gpu_utils),
            'mem_util_avg': sum(mem_utils) / len(mem_utils),
            'mem_used_avg_MiB': sum(mem_useds) / len(mem_useds),
            'mem_used_max_MiB': max(mem_useds),
            'mem_total_MiB': mem_totals[-1],
        }


# ========== 阶段计时器 ==========
class PhaseTimer:
    def __init__(self):
        self.marks = []  # [(name, t)]
        self.start_t = time.time()
        self.marks.append(('start', self.start_t))

    def mark(self, name):
        self.marks.append((name, time.time()))

    def summary(self):
        print('\n========== 阶段耗时 ==========', flush=True)
        for i in range(1, len(self.marks)):
            name, t = self.marks[i]
            prev_name, prev_t = self.marks[i-1]
            dt = t - prev_t
            print(f'  {prev_name} -> {name}: {dt:.2f}s', flush=True)
        total = self.marks[-1][1] - self.marks[0][1]
        print(f'  总耗时: {total:.2f}s', flush=True)
        return total


# ========== 实时打印 GPU 状态的线程 ==========
class LivePrinter(threading.Thread):
    def __init__(self, monitor, interval=2.0):
        super().__init__(daemon=True)
        self.monitor = monitor
        self.interval = interval
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            snap = self.monitor.snapshot()
            if snap:
                _, gpu, mem_util, mem_used, mem_total = snap
                print(f'  [GPU] util={gpu:5.1f}%  mem={mem_used:6.0f}/{mem_total:.0f} MiB '
                      f'({mem_util:.1f}%)', flush=True)
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()


# ========== 主入口 ==========
def main():
    parser = argparse.ArgumentParser(description='GPU 监控 + faceswap_tryon_pipeline 测试')
    parser.add_argument('--mode', choices=['image', 'video'], default='image')
    parser.add_argument('--input', required=True)
    parser.add_argument('--face', default=None)
    parser.add_argument('--garment', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--garment-desc', default='garment')
    parser.add_argument('--width', type=int, default=384)
    parser.add_argument('--height', type=int, default=512)
    parser.add_argument('--steps', type=int, default=20)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--skip-faceswap', action='store_true')
    parser.add_argument('--pose', default=None)
    parser.add_argument('--mask', default=None)
    parser.add_argument('--sample-interval', type=float, default=0.5,
                        help='GPU 采样间隔(秒)')
    parser.add_argument('--print-interval', type=float, default=2.0,
                        help='GPU 状态打印间隔(秒)')
    args = parser.parse_args()

    # 初始化监控
    monitor = GPUMonitor(interval=args.sample_interval)
    monitor.start()
    timer = PhaseTimer()
    printer = LivePrinter(monitor, interval=args.print_interval)
    printer.start()

    print('\n========== 测试参数 ==========', flush=True)
    print(f'  mode: {args.mode}', flush=True)
    print(f'  input: {args.input}', flush=True)
    print(f'  face: {args.face}', flush=True)
    print(f'  garment: {args.garment}', flush=True)
    print(f'  output: {args.output}', flush=True)
    print(f'  size: {args.width}x{args.height}, steps={args.steps}, seed={args.seed}', flush=True)
    print(f'  skip_faceswap: {args.skip_faceswap}', flush=True)
    print(f'  pose: {args.pose}', flush=True)
    print(f'  mask: {args.mask}', flush=True)

    # 动态导入 pipeline（导入过程会加载模型，也要监控）
    print('\n========== 导入 pipeline 模块 ==========', flush=True)
    pipeline_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'faceswap_tryon_pipeline.py')
    sys.path.insert(0, os.path.dirname(pipeline_path))

    # 导入模块（模型加载阶段）
    import importlib.util
    spec = importlib.util.spec_from_file_location('faceswap_tryon_pipeline', pipeline_path)
    pipeline_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pipeline_mod)
    timer.mark('module_imported')

    # 调用对应的处理函数
    print('\n========== 运行 pipeline ==========', flush=True)
    pre_run_idx = len(monitor.samples)

    # 把 args 转换为 pipeline 期望的 namespace
    pipeline_args = argparse.Namespace(
        mode=args.mode,
        input=args.input,
        face=args.face,
        garment=args.garment,
        output=args.output,
        garment_desc=args.garment_desc,
        width=args.width,
        height=args.height,
        steps=args.steps,
        seed=args.seed,
        skip_faceswap=args.skip_faceswap,
        pose=args.pose,
        mask=args.mask,
        # video 专用参数（给默认值）
        segment_sec=15,
        fps=None,
        keep_tmp=False,
        frame_skip=1,
        mask_mode='auto',
    )

    error_traceback = None
    try:
        if args.mode == 'image':
            pipeline_mod.process_image(pipeline_args)
        else:
            pipeline_mod.process_video(pipeline_args)
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f'\n[ERROR] pipeline 运行失败: {e}', flush=True)
        print(error_traceback, flush=True)
        timer.mark('pipeline_failed')
    else:
        timer.mark('pipeline_done')

    printer.stop()
    timer.mark('monitor_stopping')

    # 等待最后几个采样
    time.sleep(1.0)
    monitor.stop()
    timer.mark('end')

    # 输出报告
    print('\n========== GPU 利用率报告 (整个流程) ==========', flush=True)
    report_all = monitor.report(0)
    if report_all:
        print(f'  采样数: {report_all["samples"]}', flush=True)
        print(f'  GPU 利用率: avg={report_all["gpu_util_avg"]:.1f}%  '
              f'max={report_all["gpu_util_max"]:.1f}%  min={report_all["gpu_util_min"]:.1f}%', flush=True)
        print(f'  显存使用: avg={report_all["mem_used_avg_MiB"]:.0f} MiB  '
              f'max={report_all["mem_used_max_MiB"]:.0f} MiB  '
              f'total={report_all["mem_total_MiB"]:.0f} MiB', flush=True)
        print(f'  显存利用率: avg={report_all["mem_util_avg"]:.1f}%', flush=True)

    print('\n========== GPU 利用率报告 (仅 pipeline 运行阶段) ==========', flush=True)
    report_run = monitor.report(pre_run_idx)
    if report_run:
        print(f'  采样数: {report_run["samples"]}', flush=True)
        print(f'  GPU 利用率: avg={report_run["gpu_util_avg"]:.1f}%  '
              f'max={report_run["gpu_util_max"]:.1f}%  min={report_run["gpu_util_min"]:.1f}%', flush=True)
        print(f'  显存使用: avg={report_run["mem_used_avg_MiB"]:.0f} MiB  '
              f'max={report_run["mem_used_max_MiB"]:.0f} MiB', flush=True)

    timer.summary()

    # 保存 JSON 报告
    report_path = args.output + '_gpu_report.json'
    full_report = {
        'args': vars(args),
        'overall': report_all,
        'pipeline_run': report_run,
        'phases': [(n, t) for n, t in timer.marks],
        'error_traceback': error_traceback,
    }
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(full_report, f, ensure_ascii=False, indent=2, default=str)
    print(f'\nGPU 报告已保存: {report_path}', flush=True)

    # 同时把错误堆栈单独保存一份文本（方便直接查看）
    if error_traceback:
        err_path = args.output + '_error.log'
        with open(err_path, 'w', encoding='utf-8') as f:
            f.write(error_traceback)
        print(f'错误堆栈已保存: {err_path}', flush=True)


if __name__ == '__main__':
    main()
