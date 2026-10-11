# 《北宋杨家将》第 3 集《邠阳城救驾》6 组九宫格原画提示词生产指南

> **使用说明**：  
> 本集采用“多宫格电影分镜表”管线，全剧 54 镜严格划分为 6 张 3×3 九宫格高分辨率大图（Grid 01 ~ Grid 06）。  
> 每次向生图模型（Gemini / Midjourney / FLUX）提交一组提示词，单次消耗 1 次额度即可获得 9 个子镜头的关键帧，总计仅需 **6 次生图** 即可 100% 锁定全剧 54 镜首帧视觉！  
> 生成后将原画存入项目目录，运行切片脚本即可自动裁切为标准 9:16 规格（`input/yang_ep03_shot01.jpg` ~ `yang_ep03_shot54.jpg`），直接作为 ComfyUI H3 图生视频的首帧输入。  

---

## 【Grid 01】 盛极隐忧 · 五台还愿（对应 Shot 01 ~ Shot 09）

### 推荐画幅：`1:1` 或 `3:4` / 超高分辨率（4K）
```text
A 3x3 storyboard contact sheet containing 9 distinct sequential cinematic panels, Chinese traditional 2D ink wash animation style, vintage Shanghai Animation Film Studio aesthetic, mineral pigment colors (pale celadon green, raw ochre, ink black, moon white), simplified line contours on textured raw rice paper background, fine black grid lines separating the 9 panels:
Panel 1 (top-left): Extreme wide shot of the grand Song imperial carriage procession marching north through bleak northern frontier, a giant ochre-yellow imperial dragon banner fluttering violently in freezing howling wind.
Panel 2 (top-center): Medium low angle shot in the imperial court at Kaifeng, Prime Minister Kou Zhun bowing deeply on floor, desperately pleading with the Emperor not to tour the dangerous frontier.
Panel 3 (top-right): Medium shot of Emperor Taizong in golden dragon robes sitting before desk waving sleeve stubbornly, appointing Eldest Son Yang Yanping as Supreme Escort General.
Panel 4 (mid-left): Detailed medium shot of Eldest Son Yang Yanping in silver lamellar armor standing beside Emperor Taizong's royal chariot, the two men sharing striking facial resemblances in profile.
Panel 5 (center): Wide minimalist landscape shot of Mount Wutai, towering hundred-foot ink pine trees and bamboo groves shrouded in pale moon-white mountain mist.
Panel 6 (mid-right): Medium shot inside solemn Buddhist hall, master of ceremonies offering golden incense and silk banners before the sacred altar amid curling blue smoke.
Panel 7 (bottom-left): High angle low-key shot of Emperor Taizong bowing down on both knees before the towering statue of Sakyamuni Buddha, the only time the sovereign kneels.
Panel 8 (bottom-center): Medium close shot outside temple steps, treacherous eunuch whispering in the Emperor's ear about Haotian Temple near Binyang with luxurious pleasure grounds.
Panel 9 (bottom-right): Close dynamic shot of Prince the Eighth (Zhao Defang) rushing forward grabbing the Emperor's yellow silk sleeve in alarm, but the imperial carriage already turning toward Binyang.
--ar 1:1 --no photo, realistic, 3d render, western comic, modern CGI
```

---

## 【Grid 02】 幽州暗伏 · 诱敌深入（对应 Shot 10 ~ Shot 18）

### 推荐画幅：`1:1` 或 `3:4` / 超高分辨率（4K）
```text
A 3x3 storyboard contact sheet containing 9 distinct sequential cinematic panels, Chinese traditional 2D ink wash animation style, vintage Shanghai Animation Film Studio aesthetic, dark night and bleak battlefield palette (ink black, slate grey, iron bronze, muted gold), textured raw rice paper background, fine black grid lines separating the 9 panels:
Panel 1 (top-left): Night shot of a lone scout galloping violently through dark wilderness and thorny dunes toward the distant black fortress walls of Liao capital Youzhou.
Panel 2 (top-center): Interior of Youzhou grand command tent draped in giant black wolf banners, Empress Dowager Xiao sitting high on carved bronze throne with cold calculative gaze.
Panel 3 (top-right): Extreme close-up of Empress Dowager Xiao's slender pale fingers moving white ivory counting rods across a war map, placing one rod precisely on Binyang city.
Panel 4 (mid-left): Low angle medium shot of towering Liao Commander Han Yanshou in heavy iron wolf armor slamming fist on chest, eagerly accepting the mission to lead fifty thousand cavalry.
Panel 5 (center): Chilling wide shot of Binyang outskirts, dense white freezing fog rolling across plains as endless ranks of black Liao cavalry silently emerge like iron forest.
Panel 6 (mid-right): Medium shot of panic erupting around the Song imperial chariot, Emperor Taizong turning pale, shouting orders for General Yang Yanping to intercept the enemy.
Panel 7 (bottom-left): Dynamic clash shot of fierce Liao vanguard Yelu Qi swinging giant ringed broadsword against Yanping's steel spear, horses rearing with ink brush splash.
Panel 8 (bottom-center): Extreme action close-up with white flash burst, Yanping thrusting spearhead through Yelu Qi's throat, throwing the enemy vanguard off his saddle.
Panel 9 (bottom-right): Wide shot of Liao vanguard column breaking formation and retreating in false defeat, Yanping holding spear on horseback as Song soldiers cheer unaware of trap.
--ar 1:1 --no photo, realistic, 3d render, western comic, modern CGI
```

---

## 【Grid 03】 孤城合围 · 铁锁大闭（对应 Shot 19 ~ Shot 27）

### 推荐画幅：`1:1` 或 `3:4` / 超高分辨率（4K）
```text
A 3x3 storyboard contact sheet containing 9 distinct sequential cinematic panels, Chinese traditional 2D ink wash animation style, vintage Shanghai Animation Film Studio aesthetic, somber nocturnal tones with iron grey, ink black, pale ochre, and torch firelight, textured rice paper, fine black grid lines separating the 9 panels:
Panel 1 (top-left): Low angle shot of the massive stone city walls of Binyang, defensive garrison hurriedly throwing open city gates to let the panicked Song imperial entourage enter.
Panel 2 (top-center): Tracking shot of Emperor Taizong's royal carriage rushing into the deep shadowy arched gateway of Binyang, swallowed by heavy darkness.
Panel 3 (top-right): Extreme close-up of the ancient iron gears and giant wooden winch groaning as the massive bronze gates begin to swing shut together.
Panel 4 (mid-left): Dramatic close impact shot of the giant bronze gates slamming shut with iron deadbolt dropping and heavy padlock locking tightly, cut off from outside world.
Panel 5 (center): High angle panoramic night shot, tens of thousands of Liao torches forming multiple glowing fiery rings completely encircling the isolated fortress city of Binyang.
Panel 6 (mid-right): Interior night shot inside Binyang temporary palace, Emperor Taizong sitting up terrified in bed covered in cold sweat, clutching trembling chest.
Panel 7 (bottom-left): Wide shot on windswept city battlements, Emperor Taizong leaning over stone parapet looking out at the endless sea of enemy torches under dark stormy skies.
Panel 8 (bottom-center): Extreme close-up of Emperor Taizong's pale hands clutching stone battlements trembling uncontrollably, pupil dilated in sheer dread.
Panel 9 (bottom-right): Medium shot of exhausted Song soldiers through the night hoisting heavy rocks and rammed-earth logs to reinforce the ramparts to a steady rhythmic thud.
--ar 1:1 --no photo, realistic, 3d render, western comic, modern CGI
```

---

## 【Grid 04】 箭创敌首 · 决死突围（对应 Shot 28 ~ Shot 36）

### 推荐画幅：`1:1` 或 `3:4` / 超高分辨率（4K）
```text
A 3x3 storyboard contact sheet containing 9 distinct sequential cinematic panels, Chinese traditional 2D ink wash animation style, vintage Shanghai Animation Film Studio aesthetic, dramatic dawn battle palette (smoke grey, raw ochre, stark white snow, dynamic ink splash), textured rice paper, fine black grid lines separating the 9 panels:
Panel 1 (top-left): Dawn wide shot of Liao legions launching massive assault on Binyang walls, wooden siege ladders rising and catapult rocks flying through smoke.
Panel 2 (top-center): Medium shot of Eldest Son Yang Yanping standing firm on battlements, drawing a giant iron recurve bow into a full round moon, aiming downward.
Panel 3 (top-right): Extreme close action shot of arrow releasing with white ink flying brushstroke, piercing violently through Liao commander Han Yanshou's left shoulder armor.
Panel 4 (mid-left): Dynamic shot of Commander Han Yanshou roaring in agony and falling from his warhorse, Liao officers rushing in panic through arrow rain to carry him back.
Panel 5 (center): Inside royal chamber, panicked Emperor Taizong pressing vermilion imperial seal onto a blood-stained silk plea for urgent relief to General Yang Ye at Daizhou.
Panel 6 (mid-right): Medium shot of Eldest Son Yanping kneeling firmly before the Emperor, volunteering to fight through the four-sided iron encirclement alone.
Panel 7 (bottom-left): Wide shot of Binyang East Gate cracking open slightly, Yanping in silver armor bursting out on white steed like an arrow, spearing through enemy pickets.
Panel 8 (bottom-center): Dramatic clash shot in darkness, a hidden Liao lance thrusting into Yanping's side, his horse falling and Yanping tumbling into snow amid white flash burst.
Panel 9 (bottom-right): Close dynamic shot of wounded Yanping slashing with dagger, leaping onto a captured Liao horse, bleeding but galloping fiercely through enemy firelines.
--ar 1:1 --no photo, realistic, 3d render, western comic, modern CGI
```

---

## 【Grid 05】 代州警报 · 金刀赴难（对应 Shot 37 ~ Shot 45）

### 推荐画幅：`1:1` 或 `3:4` / 超高分辨率（4K）
```text
A 3x3 storyboard contact sheet containing 9 distinct sequential cinematic panels, Chinese traditional 2D ink wash animation style, vintage Shanghai Animation Film Studio aesthetic, stark northern snowstorm and heroic crimson bronze tones, textured raw rice paper, fine black grid lines separating the 9 panels:
Panel 1 (top-left): Wide bleak snowfield shot outside Daizhou fortress, a lone blood-drenched rider on dying horse galloping furiously toward the imposing northern gate.
Panel 2 (top-center): Medium shot inside Daizhou military headquarters, wounded Yanping collapsing onto stone floor holding up the blood-stained imperial rescue decree.
Panel 3 (top-right): Medium shot of veteran General Yang Ye slamming his palm down onto the purple sandalwood command desk in shock and fury, inkstone and cups jumping.
Panel 4 (mid-left): Extreme close-up of Yang Ye's hand gripping the hilt of his ancient golden sabre, unsheathing it one inch with razor-sharp steel reflection across his eyes.
Panel 5 (center): Interior shot of Yang sons gathering in fury, Seventh Son Yang Qilang stepping forward with clenched fists demanding to lead the vanguard.
Panel 6 (mid-right): Close shot of Yang Ye resting a firm weathered hand on Seventh Son's shoulder, ordering thirty thousand cavalry to mobilize immediately.
Panel 7 (bottom-left): High angle wide shot of Daizhou drill ground, crimson Yang banners surging in the wind as thirty thousand ironclad cavalry assemble with spears raised.
Panel 8 (bottom-center): Minimalist cinematic wide shot of the thirty thousand Song cavalry riding at full gallop across snowy hills like a dark winding dragon into the horizon.
Panel 9 (bottom-right): Ground-level close-up of galloping horse hooves churning up frozen snow and slush, mud splashing violently as battle banners sweep overhead.
--ar 1:1 --no photo, realistic, 3d render, western comic, modern CGI
```

---

## 【Grid 06】 阴谋让路 · 绝地死局（对应 Shot 46 ~ Shot 54）

### 推荐画幅：`1:1` 或 `3:4` / 超高分辨率（4K）
```text
A 3x3 storyboard contact sheet containing 9 distinct sequential cinematic panels, Chinese traditional 2D ink wash animation style, vintage Shanghai Animation Film Studio aesthetic, somber fateful nocturnal tones with ink black, cinnabar red torches, and desolate stone ramparts, textured rice paper, fine black grid lines separating the 9 panels:
Panel 1 (top-left): Medium shot on Liao hillock, Liao Supreme Commander Yelu Shang stroking beard with sinister cunning smile watching the Yang army banners approach in distance.
Panel 2 (top-center): Wide cinematic shot of the massive Liao army mysteriously parting like opening tides, deliberately leaving a wide open corridor straight to Binyang gate.
Panel 3 (top-right): Close shot of Sixth Son Yang Yanzhao pulling reins sharply beside his father, pointing ahead with sharp furrowed brow warning of an obvious trap.
Panel 4 (mid-left): Close-up of veteran Yang Ye looking toward Binyang with sorrowful resolute eyes, raising golden sabre and declaring they must enter to save their sovereign.
Panel 5 (center): Wide shot of Yang army charging straight into Binyang city gate, the heavy gates shutting behind them once more, sealing them all inside.
Panel 6 (mid-right): Inside Binyang palace, Emperor Taizong grasping Yang Ye's hands in tears while Yang Ye urgently bows and pleads to break out tonight before siege tightens.
Panel 7 (bottom-left): Close shot of Emperor Taizong hesitating and waving sleeve, saying roads are dangerous at night and they should rest until tomorrow morning.
Panel 8 (bottom-center): Medium shot of General Yang Ye standing alone on the cold dark city parapet, eyes closed in silent sorrow, white beard and cloak whipped by freezing wind.
Panel 9 (bottom-right): Extreme wide panoramic night shot, the parted Liao army torches suddenly surging back together in a massive scarlet crimson ring of fire, locking Binyang in inescapable doomed siege under pitch-black sky.
--ar 1:1 --no photo, realistic, 3d render, western comic, modern CGI
```

---

## 生产切片与投产执行规范

1. **生图提交**：依次复制 Grid 01 ~ Grid 06 的英文字符串至生图工具，生成 6 张超清九宫格原画。
2. **切片脚本执行**：
   ```bash
   cmd /c python tools/yangjiajiang_grid_cutter.py --input output/2026-10-08/yangjiajiang_ep03/grids/ --output input/yang_ep03/
   ```
3. **首帧导入**：自动输出的 54 张切片图片 `yang_ep03_shot01.jpg` ~ `yang_ep03_shot54.jpg` 即为全剧 54 镜的严格标准化首帧输入。
