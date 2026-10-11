import urllib.request
import json
import time
import shutil
import os

OUT_DATE = "2026-09-28"
ARTIFACT_DIR = r"C:\Users\kenzhao\.gemini\antigravity-ide\brain\eff45711-cf9b-45db-9603-8b64b900c0e7"
COMFY_OUT_DIR = rf"D:\ai_projects\ComfyUI\output\{OUT_DATE}"

os.makedirs(COMFY_OUT_DIR, exist_ok=True)

# 30 Tropical Villa Poolside Prompts
POOL_VILLA_PROMPTS = [
    # 01 - 05: 晨曦与微风白衬衫经典款
    {
        "id": "pool_villa_01_dawn_breeze",
        "title": "晨曦薄雾椰影晨光",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928501,
        "text": "Full body mirror selfie of a stunning Korean drama lead actress, slender long legs. Standing by expansive open glass sliding doors in a cliffside tropical master suite, morning dawn mist over turquoise infinity pool, lush coconut palms sway in gentle sea breeze. Wearing an unbuttoned crisp sheer white linen oversized shirt fluttering in wind, delicate lace crop top, high-waisted linen shorts, bare feet touching floor. 8k resolution, cinematic golden morning rim light."
    },
    {
        "id": "pool_villa_02_golden_hour_swim",
        "title": "黄昏无边泳池熔金波光",
        "pose": "pose_stretched_natural.png",
        "seed": 928502,
        "text": "Full body mirror selfie of a chic Korean beauty, porcelain skin, long dark hair. In a private luxury villa master suite, reflecting floor-to-ceiling glass doors open to an infinity pool sparkling with deep gold and amber sunset light, ocean horizon view. Wearing an oversized powder blue linen boyfriend shirt over a white ribbed crop tank, micro khaki shorts, slender endless legs, 8k resolution."
    },
    {
        "id": "pool_villa_03_silk_robe_pool",
        "title": "象牙真丝晨袍池畔倚栏",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928503,
        "text": "Full body mirror selfie of an elegant Korean young woman, glowing translucent fair skin. Master bedroom opening directly to the private pool terrace, clear turquoise water reflections casting caustic light patterns on ceiling. Wearing a flowing ivory silk satin draped kimono robe tied loosely at high waist, high side slit exposing slender elongated legs, bare feet, quiet luxury resort, 8k resolution."
    },
    {
        "id": "pool_villa_04_midday_crystal_water",
        "title": "正午蔚蓝通透水光倒影",
        "pose": "pose_stretched_natural.png",
        "seed": 928504,
        "text": "Full body mirror selfie of a Korean influencer. High noon bright sun over private villa infinity pool, crystal clear aquamarine water reflecting vibrant green tropical monstera and palm foliage. Wearing a tied cropped white cotton shirt, high-waisted vintage denim cutoffs, toned slim waistline, slender legs reaching bottom frame, clean tropical resort aesthetic, 8k resolution."
    },
    {
        "id": "pool_villa_05_dusk_blue_hour",
        "title": "蓝调暮色微醺泳池壁灯",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928505,
        "text": "Full body mirror selfie of a glamorous Korean actress. Blue hour dusk over tropical infinity pool, underwater warm pool lights glowing beneath indigo water, distant ocean twilight. Wearing an oversized sheer beige linen resort shirt, black bikini top, high-waisted tailored linen shorts, long slender silhouette, cinematic moody ambient lighting, 8k resolution."
    },
    # 06 - 10: 材质与穿搭变化（薄纱罩衫/针织/挂脖露背）
    {
        "id": "pool_villa_06_mint_sheer_coverup",
        "title": "薄荷绿半透明轻纱微拂",
        "pose": "pose_stretched_natural.png",
        "seed": 928506,
        "text": "Full body mirror selfie of a Korean model, radiant skin, loose bun. Tropical villa bedroom overlooking pool and lush frangipani blossoms, soft morning sunlight. Wearing an ethereal mint green sheer chiffon button-down coverup fluttering in breeze, white high-waisted shorts, slender endless legs, bare feet on bleached teak decking, 8k resolution."
    },
    {
        "id": "pool_villa_07_crochet_knit_resort",
        "title": "法式复古镂空针织罩衫",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928507,
        "text": "Full body mirror selfie of a tall slender Korean woman. Villa glass doors overlooking sun-drenched private pool terrace. Wearing an open-knit cream crochet beach cardigan over ivory bikini top, high-waisted knit micro shorts, endless slender legs, gold layered necklaces, chic bohemian resort luxury, 8k resolution."
    },
    {
        "id": "pool_villa_08_halter_linen_pool",
        "title": "纯白亚麻挂脖露腰长腿",
        "pose": "pose_stretched_natural.png",
        "seed": 928508,
        "text": "Full body mirror selfie of a Korean young woman. Poolside villa bedroom, reflection of swaying palms and glistening pool tiles. Wearing a tailored white linen halter crop top, matching high-waisted pleated linen culotte shorts, bare slender legs, delicate gold anklet, elegant quiet luxury holiday, 8k resolution."
    },
    {
        "id": "pool_villa_09_striped_boyfriend_shirt",
        "title": "法式蓝白细条纹慵懒男友衬衫",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928509,
        "text": "Full body mirror selfie of a Korean drama lead, silky dark hair. Villa master suite with panoramic infinity pool backdrop, warm golden hour sunbeams. Wearing an oversized blue and white pinstriped poplin boyfriend shirt casually unbuttoned, raw-hem denim micro shorts, slender supermodel leg proportions, 8k resolution."
    },
    {
        "id": "pool_villa_10_backless_slip_pool",
        "title": "露背香槟细吊带池畔晨曲",
        "pose": "pose_stretched_natural.png",
        "seed": 928510,
        "text": "Full body mirror selfie of a Korean beauty, fair glowing skin. Glass doors wide open to shimmering turquoise pool and tropical garden, gentle morning breeze. Wearing a champagne cowl-neck satin slip dress with deep side slit, slender shapely legs, minimalist aesthetic, 8k resolution."
    },
    # 11 - 15: 构图与光影变奏（折射水纹/椰林剪影/阳光洒肩）
    {
        "id": "pool_villa_11_water_caustics_wall",
        "title": "泳池水纹波光折射室内",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928511,
        "text": "Full body mirror selfie of a Korean actress. Shimmering animated water caustics dancing on bedroom white walls from sunny private infinity pool outside, tropical coconut palms backdrop. Wearing a lightweight open white gauze shirt over white crop top, beige micro shorts, slender long legs, bright sunlit holiday vibe, 8k resolution."
    },
    {
        "id": "pool_villa_12_sunset_silhouette_glow",
        "title": "落日逆光金边发丝轮廓",
        "pose": "pose_stretched_natural.png",
        "seed": 928512,
        "text": "Full body mirror selfie of a Korean beauty. Dramatic sunset glow framing the open glass doorway behind her, golden sun low over infinity pool edge, rich orange and violet horizon. Wearing an oversized cream linen resort shirt, denim shorts, radiant backlit rim lighting on hair and slender silhouette, 8k resolution."
    },
    {
        "id": "pool_villa_13_tropical_rain_cozy",
        "title": "海岛热带雨后池畔微润",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928513,
        "text": "Full body mirror selfie of a Korean young woman. Post-rain fresh tropical morning, glistening wet teak deck, fresh green palms and calm pool surface, misty soft diffused daylight. Wearing an oversized white cotton boyfriend shirt, grey heather high-waisted knit lounge shorts, slender legs, barefoot, serene mood, 8k resolution."
    },
    {
        "id": "pool_villa_14_straw_hat_chic",
        "title": "法式草编宽檐帽度假风",
        "pose": "pose_stretched_natural.png",
        "seed": 928514,
        "text": "Full body mirror selfie of a stylish Korean fashionista. Open pool villa master suite, sparkling blue pool water and tropical sky. Wearing a wide-brim straw hat tilted back, oversized breezy white linen shirt, high-waisted sage green shorts, slender toned legs, sun-kissed luxury vacation aesthetic, 8k resolution."
    },
    {
        "id": "pool_villa_15_floating_breakfast_view",
        "title": "水上漂浮早午餐远景",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928515,
        "text": "Full body mirror selfie of an elegant Korean heiress. Villa glass doors overlook pool where a wicker floating breakfast tray with tropical fruits rests on turquoise water, bright morning tropical sun. Wearing a crisp light azure linen shirt, white micro shorts, endless slender legs, quiet luxury resort, 8k resolution."
    },
    # 16 - 20: 奢华度假细节深化（大理石下沉式水台/柚木露台/丝质睡袍）
    {
        "id": "pool_villa_16_sunken_lounge_terrace",
        "title": "下沉式水上沙发休息区",
        "pose": "pose_stretched_natural.png",
        "seed": 928516,
        "text": "Full body mirror selfie of a Korean drama lead actress. Sliding glass doors open to sunken pool lounge fire-pit area in luxury cliffside villa, turquoise water wrapping around terrace, morning sun. Wearing an open relaxed white linen shirt over ribbed bandeau, high-cut khaki chino shorts, slender legs, 8k resolution."
    },
    {
        "id": "pool_villa_17_blush_pink_linen",
        "title": "茱萸粉轻亚麻海风低语",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928517,
        "text": "Full body mirror selfie of a sweet Korean beauty, glowing porcelain complexion. Tropical pool terrace with emerald coconut trees. Wearing an oversized blush pink garment-washed linen shirt casually draped, white high-waisted shorts, slender endless legs, soft breeze moving sheer curtains, 8k resolution."
    },
    {
        "id": "pool_villa_18_infinity_horizon_ocean",
        "title": "水天一色海平线无边泳池",
        "pose": "pose_stretched_natural.png",
        "seed": 928518,
        "text": "Full body mirror selfie of a tall Korean model. Infinite horizon where pool water merges seamlessly with ocean blue, bright sunny sky. Wearing a loose white silk resort button-down, denim micro shorts, slender long legs extending to floor, barefoot, crisp clean luxury atmosphere, 8k resolution."
    },
    {
        "id": "pool_villa_19_monochrome_minimal_pool",
        "title": "黑白极简现代建筑泳池",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928519,
        "text": "Full body mirror selfie of a chic Korean influencer. Modernist monochrome villa with black metal doorframes opening to pool, dark basalt stone tiles, pale turquoise water. Wearing a crisp white poplin shirt, black tailored high-waisted micro shorts, slender supermodel legs, architectural framing, 8k resolution."
    },
    {
        "id": "pool_villa_20_candlelight_night_pool",
        "title": "夜色烛光泳池水波漫影",
        "pose": "pose_stretched_natural.png",
        "seed": 928520,
        "text": "Full body mirror selfie of an alluring Korean actress. Nighttime villa bedroom, warm hurricane candle lanterns lining pool edge, illuminated swimming pool casting blue reflections on glass doors. Wearing an oversized silky white shirt, black shorts, slender glowing legs, romantic twilight atmosphere, 8k resolution."
    },
    # 21 - 25: 更多度假风与松弛感（随性抓拍/棉麻质感/自然侧光）
    {
        "id": "pool_villa_21_terracotta_pot_greens",
        "title": "陶土花器与热带旅人蕉",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928521,
        "text": "Full body mirror selfie of a Korean beauty, fair skin. Villa pool doorway framed by giant terracotta pots with flourishing traveler palms, crystal clear pool shimmer. Wearing an oversized white linen boyfriend shirt, high-waisted natural raw linen shorts, slender elongated legs, sunlit organic luxury, 8k resolution."
    },
    {
        "id": "pool_villa_22_lavender_linen_resort",
        "title": "浅薰衣草紫亚麻衬衫",
        "pose": "pose_stretched_natural.png",
        "seed": 928522,
        "text": "Full body mirror selfie of a Korean drama lead, lovely smile. Villa bedroom opening to calm pool terrace, morning sunlight filtering through palm fronds. Wearing an oversized pastel lavender linen shirt, white tank top, high-waisted white shorts, slender legs, quiet elegant charm, 8k resolution."
    },
    {
        "id": "pool_villa_23_canopy_bed_pool_view",
        "title": "四柱幔帐床倒映池光",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928523,
        "text": "Full body mirror selfie of an elegant Korean heiress. Master bedroom with sheer white draped four-poster bed behind her, sliding glass door open to pool water and ocean sky. Wearing an open flowing white poplin shirt, khaki micro shorts, slender endless legs, peaceful resort luxury, 8k resolution."
    },
    {
        "id": "pool_villa_24_sun_lounger_reflection",
        "title": "池畔柚木日光躺椅倒影",
        "pose": "pose_stretched_natural.png",
        "seed": 928524,
        "text": "Full body mirror selfie of a Korean fashion model. Looking out through glass doors onto pool deck with teak sun loungers, striped rolled towels, and sun umbrella. Wearing an oversized airy white gauze shirt, denim cutoffs, bare slender long legs, bright midday sunshine, 8k resolution."
    },
    {
        "id": "pool_villa_25_golden_sunset_cocktail",
        "title": "落日余晖池畔小憩",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928525,
        "text": "Full body mirror selfie of a Korean beauty. Deep warm golden sunset casting long dramatic shadows across pool terrace, sky painted pink and orange. Wearing a flowing white silk-linen shirt unbuttoned, white bandeau, denim micro shorts, slender supermodel legs, golden rim lighting, 8k resolution."
    },
    # 26 - 30: 极致九头身美感收官（海天一色/晨风扬纱/顶奢私密感）
    {
        "id": "pool_villa_26_sheer_curtains_breeze",
        "title": "薄纱幔帐随风起舞",
        "pose": "pose_stretched_natural.png",
        "seed": 928526,
        "text": "Full body mirror selfie of a Korean young woman. Floor-to-ceiling sheer white curtains billowing gently in sea breeze beside glass sliding doors, turquoise infinity pool and palms visible outside. Wearing a loose white linen button-down, micro shorts, bare slender legs, dreamy ethereal mood, 8k resolution."
    },
    {
        "id": "pool_villa_27_olive_green_linen",
        "title": "橄榄绿棉麻短裤配白衬衫",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928527,
        "text": "Full body mirror selfie of a chic Korean influencer. Cliffside villa master suite, infinity pool and tropical foliage. Wearing an oversized crisp white poplin shirt tucked casually into high-waisted olive green linen shorts, slender long legs, modern natural resort aesthetic, 8k resolution."
    },
    {
        "id": "pool_villa_28_zen_water_fountain",
        "title": "禅意水景石钵微澜",
        "pose": "pose_stretched_natural.png",
        "seed": 928528,
        "text": "Full body mirror selfie of an elegant Korean woman. Luxury villa pool edge with carved stone water spillways, smooth flowing water, lush tropical greenery. Wearing an open white cotton shirt, white tank top, beige tailored shorts, slender shapely legs, tranquil zen atmosphere, 8k resolution."
    },
    {
        "id": "pool_villa_29_sunhat_sunglasses_chic",
        "title": "黑金墨镜度假名媛风",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928529,
        "text": "Full body mirror selfie of a Korean chaebol heiress. Pool villa glass doors overlooking glittering blue pool. Wearing stylish black cat-eye sunglasses on head, oversized white linen shirt unbuttoned, tailored white shorts, slender endless legs, luxurious jewelry accents, 8k resolution."
    },
    {
        "id": "pool_villa_30_grand_finale_pool",
        "title": "绝美晨光海岛泳池全景盛宴",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928530,
        "text": "Full body mirror selfie of a breathtaking Korean actress, luminous porcelain skin, silky dark hair. Master bedroom glass doors wide open to expansive turquoise infinity pool, ocean horizon, clear blue morning sky and coconut palms. Wearing an oversized crisp white linen boyfriend shirt fluttering in breeze, white micro shorts, barefoot, ultra-long slender legs reaching floor, 8k resolution."
    }
]

# 30 Minimalist Spiral Staircase Prompts
SPIRAL_STAIRS_PROMPTS = [
    # 01 - 05: 极简纯白石膏旋转楼梯经典款
    {
        "id": "spiral_stairs_01_pure_white_sculpture",
        "title": "纯白极简流线型旋转楼梯",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928601,
        "text": "Full body mirror selfie of a stunning Korean drama lead actress, slender endless legs. Standing in the entrance foyer of a minimalist modern duplex villa, dramatic pure white sculptural spiral staircase curving upwards in background, seamless travertine stone floor with gentle soft reflection. Wearing a structured cream tailored blazer over black crop top, high-waisted micro skirt, pointed slingbacks, 8k resolution."
    },
    {
        "id": "spiral_stairs_02_skylight_natural_beam",
        "title": "圆形穹顶天窗倾泻天光",
        "pose": "pose_stretched_natural.png",
        "seed": 928602,
        "text": "Full body mirror selfie of an elegant Korean heiress, glowing porcelain skin. Modern architectural villa foyer, sweeping white spiral staircase beneath an expansive circular glass skylight casting dramatic clean geometric daylight. Wearing a high-waisted charcoal grey tailored trouser suit with crop jacket, slender long legs, minimalist quiet luxury, 8k resolution."
    },
    {
        "id": "spiral_stairs_03_little_black_dress_stair",
        "title": "黑裙白梯极致视觉张力",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928603,
        "text": "Full body mirror selfie of a glamorous Korean actress, delicate collarbones. Full-length mirror in grand villa foyer, pure white spiral staircase sweeping upward in background creating dramatic monochrome contrast. Wearing a structured off-the-shoulder black crepe mini dress, high waist, slender supermodel legs, black patent pointed stilettos, 8k resolution."
    },
    {
        "id": "spiral_stairs_04_floating_steps_minimal",
        "title": "悬挑悬空极简踏步与光带",
        "pose": "pose_stretched_natural.png",
        "seed": 928604,
        "text": "Full body mirror selfie of a chic Korean art curator. Modern luxury home foyer, cantilevered floating white spiral staircase steps with hidden LED warm under-step glow, polished light limestone floor. Wearing a minimalist oversized beige trench coat over black turtleneck and leather shorts, slender legs, ankle boots, 8k resolution."
    },
    {
        "id": "spiral_stairs_05_curved_handrail_smooth",
        "title": "无立柱一体化雕塑感扶手",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928605,
        "text": "Full body mirror selfie of a tall Korean fashion model. Duplex penthouse entrance hall, sweeping continuous curved white plaster spiral staircase banister ascending like modern art sculpture, soft ambient lighting. Wearing an oversized white poplin shirt tucked into vintage blue high-waisted denim shorts, endless slender legs, 8k resolution."
    },
    # 06 - 10: 材质混搭（浅木踏步/灰调微水泥/清澈水台）
    {
        "id": "spiral_stairs_06_oak_tread_white_spine",
        "title": "浅色白橡木踏步与纯白龙骨",
        "pose": "pose_stretched_natural.png",
        "seed": 928606,
        "text": "Full body mirror selfie of a Korean beauty, radiant skin. Villa entrance foyer with curved spiral staircase featuring pale white oak wood steps and smooth white ribbon railing, soft morning sun. Wearing an oatmeal cashmere slouchy cardigan, cream knit shorts, bare slender legs, warm scandinavian minimalist luxury, 8k resolution."
    },
    {
        "id": "spiral_stairs_07_concrete_microcement_foyer",
        "title": "浅灰微水泥现代建筑质感",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928607,
        "text": "Full body mirror selfie of a trendy Korean influencer. Architectural studio entrance hall, seamless light grey microcement spiral staircase curving upward, matte black steel doorframe reflections, polished concrete floor. Wearing a black halter top, tailored wide-leg khaki trousers, slender elongated silhouette, 8k resolution."
    },
    {
        "id": "spiral_stairs_08_indoor_fountain_base",
        "title": "旋转楼梯底口镜面浅水景",
        "pose": "pose_stretched_natural.png",
        "seed": 928608,
        "text": "Full body mirror selfie of a Korean actress. Luxury villa foyer with circular shallow indoor reflecting pool at base of soaring white spiral staircase, tranquil black pebble border. Wearing a cobalt blue silk shirt, white high-waisted shorts, slender shapely legs, nude pointed heels, 8k resolution."
    },
    {
        "id": "spiral_stairs_09_chaebol_tweed_grand_foyer",
        "title": "名媛粗花呢套装与尊贵大堂",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928609,
        "text": "Full body mirror selfie of a Korean chaebol heiress. Grand duplex manor entrance, sweeping double-height white spiral staircase, crystal orb pendant light cluster. Wearing a pastel cream textured tweed cropped jacket, matching A-line tweed mini skirt, slender endless legs, black Mary Jane kitten heels, 8k resolution."
    },
    {
        "id": "spiral_stairs_10_glass_railing_translucent",
        "title": "极简无框曲面玻璃扶手",
        "pose": "pose_stretched_natural.png",
        "seed": 928610,
        "text": "Full body mirror selfie of a Korean young woman. Minimalist architectural villa foyer, curved continuous glass spiral staircase balustrade, floating white steps, clean light reflections. Wearing a crisp white poplin shirt, raw denim micro shorts, slender long legs, modern high-fashion aesthetic, 8k resolution."
    },
    # 11 - 15: 光影与空间层次（斜射午后阳光/艺术吊灯/挑高两层）
    {
        "id": "spiral_stairs_11_afternoon_sun_stripes",
        "title": "斜射百叶阳光光栅影调",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928611,
        "text": "Full body mirror selfie of a Korean beauty. Double-height villa foyer, afternoon sun slicing through tall slatted windows creating graphic diagonal light and shadow stripes across white spiral staircase. Wearing an ivory silk camisole slip dress with thigh slit, slender supermodel legs, artistic cinematic lighting, 8k resolution."
    },
    {
        "id": "spiral_stairs_12_pendant_chandelier_cascade",
        "title": "垂直垂落极简水滴吊灯群",
        "pose": "pose_stretched_natural.png",
        "seed": 928612,
        "text": "Full body mirror selfie of a Korean drama lead actress. Villa entryway with tall spiral staircase spiraling around a vertical cascade of delicate blown-glass drop pendant lights, warm ambient illumination, polished travertine floor. Wearing a tailored cream blazer, black micro skirt, slender long legs, 8k resolution."
    },
    {
        "id": "spiral_stairs_13_terrazzo_floor_reflection",
        "title": "浅米色磨石子通透倒影",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928613,
        "text": "Full body mirror selfie of a tall Korean model. Modernist villa foyer, seamless cream Venetian terrazzo floor reflecting the organic curves of a pure white spiral staircase. Wearing a black ribbed racerback tank top, high-waisted pleated wide-leg trousers, slender elongated frame, 8k resolution."
    },
    {
        "id": "spiral_stairs_14_ficus_tree_indoor_garden",
        "title": "梯下绿植庭院与大叶琴叶榕",
        "pose": "pose_stretched_natural.png",
        "seed": 928614,
        "text": "Full body mirror selfie of a Korean beauty, fair skin. Atrium villa foyer, a tall architectural Ficus Lyrata tree growing beneath the sweeping curve of a white spiral staircase, bright diffused natural skylight. Wearing an oversized white linen shirt, beige shorts, slender legs, fresh serene luxury, 8k resolution."
    },
    {
        "id": "spiral_stairs_15_curved_niche_recessed_art",
        "title": "弧形壁龛内嵌艺术雕塑",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928615,
        "text": "Full body mirror selfie of a Korean actress. Duplex art collector home foyer, soft curved plaster walls with warm back-lit niches framing a soaring white spiral staircase. Wearing an elegant off-shoulder black knit top, high-waisted white cigarette pants, pointed kitten heels, slender legs, 8k resolution."
    },
    # 16 - 20: 晚间氛围与奢华夜景（暗调微光/底灯渲染/冷艳高贵）
    {
        "id": "spiral_stairs_16_evening_dramatic_uplight",
        "title": "夜景地埋射灯仰照楼梯腹面",
        "pose": "pose_stretched_natural.png",
        "seed": 928616,
        "text": "Full body mirror selfie of a Korean beauty. Nighttime luxury villa foyer, warm recessed floor uplights casting sculptural shadows along the smooth underside of the white spiral staircase, moody dark architectural luxury. Wearing a structured black mini dress, bare slender legs, black stilettos, 8k resolution."
    },
    {
        "id": "spiral_stairs_17_marble_bookmatch_wall",
        "title": "对拼雪花白大理石背景墙",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928617,
        "text": "Full body mirror selfie of a Korean heiress. Grand duplex foyer, sweeping white spiral staircase set against a two-story bookmatched Statuario marble feature wall with delicate grey veining. Wearing an azure silk blouse, high-waisted tailored khaki shorts, slender endless legs, quiet wealth, 8k resolution."
    },
    {
        "id": "spiral_stairs_18_golden_brass_accents",
        "title": "拉丝香槟金踢脚与金属收边",
        "pose": "pose_stretched_natural.png",
        "seed": 928618,
        "text": "Full body mirror selfie of an elegant Korean young woman. Minimalist foyer, curved white spiral staircase finished with subtle brushed champagne brass edge trim, warm ambient glow. Wearing a fitted knit polo crop top, white pleated tennis skirt, crew socks, slender long legs, 8k resolution."
    },
    {
        "id": "spiral_stairs_19_monolithic_stone_block",
        "title": "首阶一体化整石起步台",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928619,
        "text": "Full body mirror selfie of a tall Korean fashion influencer. Architectural villa entrance, monolithic floating curved marble block base starting the spiral staircase, pure white walls. Wearing an oversized white boyfriend shirt unbuttoned, raw denim cutoffs, slender supermodel legs, 8k resolution."
    },
    {
        "id": "spiral_stairs_20_curved_fluted_wall",
        "title": "法式复古竖纹格栅曲面墙",
        "pose": "pose_stretched_natural.png",
        "seed": 928620,
        "text": "Full body mirror selfie of a Korean actress. Duplex penthouse foyer with fluted plaster curved wall echoing the spiral staircase trajectory, soft morning sunlight. Wearing an oversized honey trench coat open, black top, leather shorts, slender shapely legs, ankle boots, 8k resolution."
    },
    # 21 - 25: 穿搭多维度升级（法式条纹/丝绒/大版男友西装）
    {
        "id": "spiral_stairs_21_navy_striped_knit",
        "title": "法式海军风条纹软糯针织",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928621,
        "text": "Full body mirror selfie of a Korean young woman, sweet natural charm. Foyer with sweeping white spiral staircase, bright sunny day. Wearing a classic navy and cream striped boatneck knit top, high-waisted white denim shorts, bare slender endless legs, casual chic quiet luxury, 8k resolution."
    },
    {
        "id": "spiral_stairs_22_emerald_silk_blouse",
        "title": "祖母绿真丝衬衫贵气千金",
        "pose": "pose_stretched_natural.png",
        "seed": 928622,
        "text": "Full body mirror selfie of a Korean drama lead actress, fair skin. Villa foyer with pure white spiral staircase. Wearing an unbuttoned rich emerald green silk shirt, black bandeau, high-waisted white tailored shorts, slender legs, gold necklace, striking color contrast, 8k resolution."
    },
    {
        "id": "spiral_stairs_23_trench_coat_belted_stair",
        "title": "经典英伦风衣系带立挺身姿",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928623,
        "text": "Full body mirror selfie of a Korean fashion model. Villa entrance hall, dramatic white spiral staircase curving upward in background. Wearing a classic beige cotton-gabardine trench coat with sleeves pushed up, micro shorts, sheer dark tights, slender supermodel legs, sleek pointed heels, 8k resolution."
    },
    {
        "id": "spiral_stairs_24_pastel_blue_knit_set",
        "title": "雾霾蓝羊绒针织套装",
        "pose": "pose_stretched_natural.png",
        "seed": 928624,
        "text": "Full body mirror selfie of a lovely Korean beauty. Light-filled duplex foyer, white spiral staircase and limestone floor. Wearing a slouchy dusty blue cashmere button-up cardigan, matching high-waisted knit shorts, bare slender legs, cozy minimalist luxury, 8k resolution."
    },
    {
        "id": "spiral_stairs_25_black_blazer_micro_shorts",
        "title": "干练黑西装内搭白色短打",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928625,
        "text": "Full body mirror selfie of a Korean chaebol daughter. Architectural foyer with pure white spiral staircase. Wearing an oversized sharp black wool blazer, white cropped ribbed tank, high-waisted black micro shorts, slender supermodel legs, silver slingback heels, 8k resolution."
    },
    # 26 - 30: 巅峰气场与视觉冲击（双层大挑空/全景落地镜/超模长腿）
    {
        "id": "spiral_stairs_26_double_height_foyer_grand",
        "title": "8米大挑空全景气场宏大",
        "pose": "pose_stretched_natural.png",
        "seed": 928626,
        "text": "Full body mirror selfie of a Korean actress. Soaring eight-meter double-height modern villa entrance foyer, monumental white spiral staircase coiling dramatically upward, expansive floor-to-ceiling windows with garden view. Wearing a blue linen boyfriend shirt, khaki shorts, slender legs, 8k resolution."
    },
    {
        "id": "spiral_stairs_27_all_white_monochrome_luxe",
        "title": "全白纯净单色极简盛宴",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928627,
        "text": "Full body mirror selfie of a tall Korean fashion influencer. All-white minimalist villa entryway, pure white spiral staircase, white marble floor, immaculate white walls. Wearing an oversized white silk shirt, tailored white shorts, nude pointed heels, endless slender legs, editorial high fashion, 8k resolution."
    },
    {
        "id": "spiral_stairs_28_warm_timber_ceiling_accent",
        "title": "暖色木格栅吊顶与白梯映衬",
        "pose": "pose_stretched_natural.png",
        "seed": 928628,
        "text": "Full body mirror selfie of an elegant Korean woman. Modern villa foyer, warm natural cedar wood slatted ceiling contrasting against the fluid white spiral staircase and polished stone floor. Wearing a cream silk blouse, khaki micro shorts, slender shapely legs, 8k resolution."
    },
    {
        "id": "spiral_stairs_29_rainy_day_moody_atrium",
        "title": "雨日静谧天光与冷调反光",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928629,
        "text": "Full body mirror selfie of a Korean beauty, porcelain skin. Villa foyer on a rainy afternoon, soft cool diffused natural light filtering through frosted skylight onto white spiral staircase, calm moody atmosphere. Wearing an oversized black boyfriend blazer, black shorts, endless slender legs, 8k resolution."
    },
    {
        "id": "spiral_stairs_30_grand_finale_staircase",
        "title": "绝美极简旋转楼梯终章大片",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928630,
        "text": "Full body mirror selfie of a breathtaking Korean drama lead actress, silky dark hair, porcelain skin. Foyer of an architectural trophy villa, sculptural white spiral staircase curving gracefully toward heaven, warm sunbeams illuminating polished stone floor. Wearing a crisp sky blue linen shirt, high-waisted khaki shorts, ultra-long slender supermodel legs reaching floor, nude kitten heels, 8k resolution."
    }
]

def build_prompt(item, subfolder_prefix):
    return {
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
                "text": item["text"],
                "clip": ["20", 1]
            }
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "short legs, dwarf proportions, stubby legs, disproportionate body, extra limbs, bad hands, deformed feet, blurry, low quality, oversaturated",
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
                "image": item["pose"]
            }
        },
        "33": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": ["10", 0],
                "negative": ["11", 0],
                "control_net": ["31", 0],
                "image": ["32", 0],
                "strength": 0.78,
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
                "seed": item["seed"],
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
                "filename_prefix": f"{OUT_DATE}/{item['id']}",
                "images": ["8", 0]
            }
        }
    }

def run_group(items, group_name, current_offset=0, total_all=60):
    print(f"\n==========================================")
    print(f"Starting {group_name} ({len(items)} items)...")
    print(f"==========================================")
    
    results = []
    for idx, item in enumerate(items, 1):
        global_idx = current_offset + idx
        print(f"\n[{global_idx}/{total_all}] ({idx}/{len(items)}) Submitting {item['id']} ({item['title']})...")
        prompt = build_prompt(item, OUT_DATE)
        req = urllib.request.Request(
            'http://127.0.0.1:8188/prompt',
            data=json.dumps({'prompt': prompt}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        res = urllib.request.urlopen(req)
        prompt_id = json.loads(res.read())['prompt_id']
        print(f"Queued prompt_id: {prompt_id}. Waiting for completion...")
        
        start_t = time.time()
        while True:
            time.sleep(3)
            try:
                h_req = urllib.request.urlopen(f'http://127.0.0.1:8188/history/{prompt_id}')
                history = json.loads(h_req.read())
                if prompt_id in history:
                    elapsed = time.time() - start_t
                    out = history[prompt_id].get('outputs', {})
                    saved_images = out.get('9', {}).get('images', [])
                    if saved_images:
                        fname = saved_images[0]['filename']
                        sub = saved_images[0].get('subfolder', '')
                        full_path = os.path.join(r"D:\ai_projects\ComfyUI\output", sub, fname)
                        artifact_dest = os.path.join(ARTIFACT_DIR, fname)
                        if os.path.exists(full_path):
                            shutil.copy2(full_path, artifact_dest)
                        print(f"-> SUCCESS [{global_idx}/{total_all}] in {elapsed:.1f}s: {fname}")
                        results.append({
                            "global_idx": global_idx,
                            "id": item["id"],
                            "title": item["title"],
                            "filename": fname,
                            "path": full_path,
                            "artifact": artifact_dest
                        })
                    else:
                        print(f"-> WARNING: Finished without output image?")
                    break
            except Exception as e:
                pass
        
        # Save progress after each single image
        try:
            with open(r"d:\ai_projects\ComfyUI\agy_veos\progress_60.json", "w", encoding="utf-8") as pf:
                json.dump({"completed": global_idx, "total": total_all, "last_image": item["id"]}, pf, indent=2)
        except:
            pass

    return results

if __name__ == "__main__":
    print(f"Starting 60-Image Batch: 30 Pool Villa + 30 Spiral Staircase...")
    pool_results = run_group(POOL_VILLA_PROMPTS, "Theme 1: 30 Pool Villa", current_offset=0, total_all=60)
    stairs_results = run_group(SPIRAL_STAIRS_PROMPTS, "Theme 2: 30 Spiral Staircase", current_offset=30, total_all=60)
    
    print("\nAll 60 images successfully generated!")
    with open(r"d:\ai_projects\ComfyUI\agy_veos\batch_60_results.json", "w", encoding="utf-8") as f:
        json.dump({"pool_villa": pool_results, "spiral_stairs": stairs_results}, f, ensure_ascii=False, indent=2)
    print("Saved batch_60_results.json")
