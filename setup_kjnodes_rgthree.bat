@echo off
cd /d D:\ai_projects\ComfyUI\custom_nodes

echo Step 1: 启用 ComfyUI-KJNodes
if exist "ComfyUI-KJNodes.disabled" (
  ren "ComfyUI-KJNodes.disabled" "ComfyUI-KJNodes"
  echo [OK] KJNodes 已启用
) else (
  echo [SKIP] KJNodes.disabled 不存在
)

echo.
echo Step 2: 启用 rgthree-comfy
if exist "rgthree-comfy.disabled" (
  ren "rgthree-comfy.disabled" "rgthree-comfy"
  echo [OK] rgthree-comfy 已启用
) else (
  echo [SKIP] rgthree-comfy.disabled 不存在
)

echo.
echo ========================================
echo 两个节点包已启用。请重启 ComfyUI 加载。
echo ========================================
pause
