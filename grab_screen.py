
import time
import os
from PIL import ImageGrab

time.sleep(2)  # 等图片查看器显示
screen = ImageGrab.grab(all_screens=True)
temp_dir = os.environ['TEMP']
path = os.path.join(temp_dir, 'desktop_view.png')
screen.save(path)
print(f'Screenshot saved: {path}, size: {screen.size}')
