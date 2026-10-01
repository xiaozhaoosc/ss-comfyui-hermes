
Add-Type -AssemblyName System.Drawing
$paths = @(
  'd:\ai_projects\ComfyUI\output\test_idm_vton_v3_20260814_00001_.png',
  'd:\ai_projects\ComfyUI\output\test_idm_vton_pose_v3_20260814_00001_.png',
  'd:\ai_projects\ComfyUI\output\test_idm_vton_mask_v3_20260814_00001_.png',
  'd:\ai_projects\ComfyUI\output\mimicmotion_test_short_v2_00001.png',
  'd:\ai_projects\ComfyUI\output\tryon_result_00005_.png',
  'd:\ai_projects\ComfyUI\output\test_faceswap_v2_20260814.png',
  'd:\ai_projects\ComfyUI\input\pics\test_frame_001.png',
  'd:\ai_projects\ComfyUI\input\todo\face\ken4.png'
)
$results = @()
foreach ($path in $paths) {
  try {
    $img = [System.Drawing.Image]::FromFile($path)
    $info = [PSCustomObject]@{
      Name = (Split-Path $path -Leaf)
      Width = $img.Width
      Height = $img.Height
      PixelFormat = $img.PixelFormat.ToString()
      SizeMB = [math]::Round((Get-Item $path).Length / 1MB, 2)
      HRes = $img.HorizontalResolution
      VRes = $img.VerticalResolution
    }
    $results += $info
    $img.Dispose()
  } catch {
    $results += [PSCustomObject]@{ Name = (Split-Path $path -Leaf); Error = $_.Exception.Message }
  }
}
$results | ConvertTo-Json -Depth 3
