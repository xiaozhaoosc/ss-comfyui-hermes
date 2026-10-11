import os
import subprocess
import cv2

FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
BASE_DIR = r"D:\ai_projects\ComfyUI\output\2026-10-04\motion_transfer_test"
CHUNKS_DIR = os.path.join(BASE_DIR, "chunks")
BGM_PATH = r"D:\ai_projects\ComfyUI\input\ken4\face\bgm原创\Calling_Through_The_Screen (1).mp3"

cases = [
    {
        "name": "mode1_case1_look1",
        "chunk": "mode1_case1_look1_chk0_raw16_00001_.mp4",
        "out": "mode1_case1_look1_10s.mp4"
    },
    {
        "name": "mode1_case2_bathroom",
        "chunk": "mode1_case2_bathroom_chk0_raw16_00001_.mp4",
        "out": "mode1_case2_bathroom_10s.mp4"
    },
    {
        "name": "mode1_case3_sailor",
        "chunk": "mode1_case3_sailor_chk0_raw16_00001_.mp4",
        "out": "mode1_case3_sailor_10s.mp4"
    },
    {
        "name": "mode2_case4_redslip",
        "chunk": "mode2_case4_redslip_chk0_raw16_00001_.mp4",
        "out": "mode2_case4_redslip_10s.mp4"
    },
    {
        "name": "mode2_case5_refimage",
        "chunk": "mode2_case5_refimage_chk0_raw16_00001_.mp4",
        "out": "mode2_case5_refimage_10s.mp4"
    },
    {
        "name": "mode2_case6_model1",
        "chunk": "mode2_case6_model1_chk0_raw16_00001_.mp4",
        "out": "mode2_case6_model1_10s.mp4"
    }
]

print("=== Assembling 6 x 10s Motion Transfer Videos ===")
results = []
for c in cases:
    src_chunk = os.path.join(CHUNKS_DIR, c["chunk"])
    dst_video = os.path.join(BASE_DIR, c["out"])
    if not os.path.exists(src_chunk):
        print(f"[Error] Source chunk not found: {src_chunk}")
        continue
    
    # Create concat list for 3 iterations (3 x 3.31s = 9.93s ~ 10s)
    tmp_list = dst_video + ".txt"
    with open(tmp_list, "w", encoding="utf-8") as f:
        for _ in range(3):
            f.write(f"file '{os.path.abspath(src_chunk)}'\n")
            
    # Concat and mix with BGM if available
    cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", tmp_list
    ]
    if os.path.exists(BGM_PATH):
        cmd.extend(["-stream_loop", "-1", "-i", BGM_PATH, "-map", "0:v:0", "-map", "1:a:0", "-shortest"])
    cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", dst_video])
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(tmp_list):
        os.remove(tmp_list)
        
    if os.path.exists(dst_video):
        cap = cv2.VideoCapture(dst_video)
        fps = cap.get(cv2.CAP_PROP_FPS)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        dur = n / fps if fps > 0 else 0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        sz = os.path.getsize(dst_video) / 1024 / 1024
        print(f"[Success] {c['name']} -> {dst_video}")
        print(f"          Duration: {dur:.2f}s, Resolution: {w}x{h}, Frames: {n}, FPS: {fps:.1f}, Size: {sz:.2f}MB")
        results.append((c['name'], dst_video, dur, w, h, sz))
    else:
        print(f"[Failed] FFmpeg error on {c['name']}: {res.stderr[:200]}")

print(f"\nTotal completed videos: {len(results)} / 6")
