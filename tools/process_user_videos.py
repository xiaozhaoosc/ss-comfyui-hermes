import os
import subprocess
import cv2

FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
BGM = r"D:\ai_projects\ComfyUI\input\ken4\face\bgm原创\Calling_Through_The_Screen (1).mp3"

out_dir = r"D:\ai_projects\ComfyUI\output\2026-10-08\motion_transfer"
os.makedirs(out_dir, exist_ok=True)

v_ig18 = r"D:\ai_projects\ComfyUI\output\2026-10-04\motion_transfer\ig18_user_test_00001_.mp4"
v_ig14 = r"D:\ai_projects\ComfyUI\output\2026-10-08\motion_transfer\ig14_user_test_00001_.mp4"

src_ig18 = r"C:\Users\kenzhao\Downloads\Instagram18_video.mp4"
src_ig14 = r"C:\Users\kenzhao\Downloads\Instagram14_video.mp4"

pose_ig18 = r"D:\ai_projects\ComfyUI\input\motion_poses\ig18_user_test\ig18_user_test_pose_pure.mp4"
pose_ig14 = r"D:\ai_projects\ComfyUI\input\motion_poses\ig14_user_test\ig14_user_test_pose_pure.mp4"

char_img = r"D:\ai_projects\ComfyUI\input\005-822807425_18090503405430819_9034340549182780041_n.jpeg"

print("1. Extracting preview frames...")
for name, p in [('ig18', v_ig18), ('ig14', v_ig14)]:
    if os.path.exists(p):
        cap = cv2.VideoCapture(p)
        ret, frame = cap.read()
        if ret:
            prev_path = os.path.join(out_dir, f"preview_{name}.jpg")
            cv2.imwrite(prev_path, frame)
            print(f"Saved {prev_path}, frame size: {frame.shape}")
        cap.release()

print("\n2. Creating stitched combined sequence (ig18 + ig14)...")
concat_txt = os.path.join(out_dir, "concat_list.txt")
combined_out = os.path.join(out_dir, "instagram_user_combined_stitched.mp4")

with open(concat_txt, "w", encoding="utf-8") as f:
    f.write(f"file '{v_ig18}'\n")
    f.write(f"file '{v_ig14}'\n")

cmd = [
    FFMPEG, "-y",
    "-f", "concat", "-safe", "0",
    "-i", concat_txt
]
if os.path.exists(BGM):
    cmd.extend(["-stream_loop", "-1", "-i", BGM, "-map", "0:v:0", "-map", "1:a:0", "-shortest"])
cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", combined_out])

subprocess.run(cmd, capture_output=True, text=True)
if os.path.exists(concat_txt):
    os.remove(concat_txt)

if os.path.exists(combined_out):
    cap = cv2.VideoCapture(combined_out)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur = cnt / fps if fps > 0 else 0
    cap.release()
    print(f"Combined video created: {combined_out}")
    print(f"  {w}x{h}, {cnt} frames, {fps:.1f} fps, {dur:.2f}s, {os.path.getsize(combined_out)/1024/1024:.2f}MB")

print("\n3. Creating Side-by-Side Comparison for IG18 and IG14...")
for tag, src, pose, gen in [
    ("ig18", src_ig18, pose_ig18, v_ig18),
    ("ig14", src_ig14, pose_ig14, v_ig14)
]:
    cmp_out = os.path.join(out_dir, f"{tag}_side_by_side_comparison.mp4")
    # Layout: Left = Ref Video (scaled 480x832), Middle = Pose (480x832), Right = Result (480x832)
    # Total width = 480*3 = 1440, height = 832
    filter_complex = (
        "[0:v]scale=480:832:force_original_aspect_ratio=decrease,pad=480:832:(ow-iw)/2:(oh-ih)/2[v0];"
        "[1:v]scale=480:832[v1];"
        "[2:v]scale=480:832[v2];"
        "[v0][v1][v2]hstack=inputs=3[outv]"
    )
    cmd = [
        FFMPEG, "-y",
        "-i", src,
        "-i", pose,
        "-i", gen,
    ]
    if os.path.exists(BGM):
        cmd.extend(["-stream_loop", "-1", "-i", BGM])
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-t", "1.77",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p"
    ])
    if os.path.exists(BGM):
        cmd.extend(["-map", "3:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"])
    cmd.append(cmp_out)
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(cmp_out):
        cap = cv2.VideoCapture(cmp_out)
        cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        dur = cnt / cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 0
        cap.release()
        print(f"Comparison created: {cmp_out}")
        print(f"  {w}x{h}, {cnt} frames, {dur:.2f}s, {os.path.getsize(cmp_out)/1024/1024:.2f}MB")
    else:
        print(f"Failed to create comparison {tag}: {res.stderr[:300]}")
