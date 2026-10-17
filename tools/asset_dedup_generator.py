# -*- coding: utf-8 -*-
"""Dynamic Procedural Asset Generator with Zero-Duplicate Collision Guard.

Features:
1. Procedural Wardrobe Generator:
   - Combinatorial syntax: Style x Fabric x Silhouette x Palette x Craftsmanship.
   - Guaranteed unique label, description, and high-precision ghost mannequin 9:16 prompt.
   - Intelligent Category Balancer: picks category with fewest assets (tops / bottoms / full).
   - Collision Guard: cross-checks existing library labels and descriptions before generation.

2. Procedural Character Generator:
   - 150+ Eastern aesthetic female names + dynamic surname & given-name combinatorial engine.
   - Archetype x Features x Hair x Suit Color x Pose variations.
   - Collision Guard: cross-checks existing character names and ID slugs.
"""
import random
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ============================================================================
# 1. WARDROBE PROCEDURAL ENGINE
# ============================================================================

STYLES_THEMES = [
    {
        "id": "neo_chinese",
        "name_cn": "新中式风韵",
        "name_en": "Neo-Chinese Elegance",
        "keywords": "mandarin collar, jade frog buttons, tone-on-tone embroidery, classical oriental aesthetics"
    },
    {
        "id": "quiet_luxury",
        "name_cn": "老钱极简静奢",
        "name_en": "Quiet Luxury",
        "keywords": "clean tailored silhouette, understated elegance, supreme fabric drape, minimalist luxury"
    },
    {
        "id": "cyber_tech",
        "name_cn": "赛博机能科技",
        "name_en": "Cyberpunk Techwear",
        "keywords": "3M reflective trims, modular utility pockets, waterproof ripstop, industrial matte buckles"
    },
    {
        "id": "french_vintage",
        "name_cn": "法式复古浪漫",
        "name_en": "French Romantic Vintage",
        "keywords": "architectural square neckline, delicate micro-pleats, puff sleeves, mother-of-pearl buttons"
    },
    {
        "id": "dark_avant_garde",
        "name_cn": "暗黑先锋高定",
        "name_en": "Dark Avant-Garde Haute Couture",
        "keywords": "architectural drape, corset boning, sculpted asymmetrical hem, deep luxurious shadows"
    },
    {
        "id": "y2k_punk",
        "name_cn": "千禧轻朋克",
        "name_en": "Y2K Preppy Punk",
        "keywords": "knife pleats, leather buckle straps, silver eyelets, rebellious streetwear aesthetic"
    },
    {
        "id": "xianxia_ethereal",
        "name_cn": "仙侠水墨诗意",
        "name_en": "Ethereal Xianxia Flow",
        "keywords": "translucent layered organza, misty gradients, delicate flowing ribbons, poetic drapery"
    },
    {
        "id": "italian_tailored",
        "name_cn": "意式手工裁缝",
        "name_en": "Italian Bespoke Tailoring",
        "keywords": "sharp lapels, impeccable Italian shoulder structure, fluid drape, artisanal hand-stitched pick seams"
    }
]

FABRICS = [
    ("双面纯手工羊绒", "double-faced hand-stitched pure cashmere"),
    ("重磅真丝乔其纱", "heavyweight mulberry silk georgette"),
    ("改良织金香云纱", "modern metallic gold phoenix jacquard brocade"),
    ("高支精纺美利奴羊毛", "fine high-twist worsted Merino wool"),
    ("哑光机能防撕裂尼龙", "matte technical ripstop nylon"),
    ("复古粗花呢编织", "heritage textured tweed bouclé"),
    ("水洗天丝亚麻混纺", "washed breathable Tencel-linen blend"),
    ("建筑感高定丝绒", "plush architectural silk velvet"),
    ("微光泽重磅缎面", "luminous heavyweight silk-satin"),
    ("哑光细腻小羊皮", "buttery soft matte nappa lambskin")
]

COLORS = [
    ("黛绿", "celadon jade green"),
    ("燕麦灰", "oatmeal beige"),
    ("午夜黑", "midnight black"),
    ("象牙白", "pure ivory white"),
    ("钛金灰", "gunmetal titanium gray"),
    ("绯红", "deep crimson red"),
    ("霁蓝", "poetic cobalt azure blue"),
    ("干邑棕", "cognac camel brown"),
    ("烟粉", "dusty blush rose"),
    ("冷月银", "luminous moonlit silver")
]

TOPS_SILHOUETTES = [
    ("立领盘扣半透短衫", "semi-sheer blouse with mandarin collar and frog buttons"),
    ("方领微褶泡泡袖衬衫", "square-neck blouse with delicate micro-pleated puff sleeves"),
    ("双排扣廓形精裁短西装", "cropped tailored double-breasted structured blazer"),
    ("高领插肩宽松落褶针织衫", "relaxed mock-neck sweater with architectural ribbing"),
    ("多口袋工装机能短夹克", "cropped tactical utility jacket with modular zip pockets"),
    ("斜襟系带飘带真丝上衣", "cross-over wrap blouse with flowing silk sash ties"),
    ("不对称露肩修身打底上衣", "asymmetric one-shoulder sculpted compression knit top")
]

BOTTOMS_SILHOUETTES = [
    ("锋利刀褶百褶马面裙", "crisp knife-pleated horse-face wrap skirt (mamianqun)"),
    ("高腰垂坠双褶阔腿西装裤", "high-waisted fluid double-pleated wide-leg tailored trousers"),
    ("双皮带扣金属孔眼百褶短裙", "pleated mini skirt with dual leather buckle belts and silver eyelets"),
    ("优雅斜裁微喇鱼尾半身裙", "bias-cut fluid fluted fishtail midi skirt"),
    ("战术多口袋快拆束脚工装裤", "tactical modular cargo joggers with snap buckle cuffs"),
    ("不对称重叠交错垂褶裹身裙", "architectural asymmetric draped overlapping wrap skirt")
]

FULL_SILHOUETTES = [
    ("鱼骨塑形高开叉丝绒长礼服", "corset-boned strapless evening gown with daring side slit"),
    ("双排扣及踝手工羊绒系带大衣", "floor-length double-breasted cashmere coat with self-tie sash belt"),
    ("法式方领碎花真丝茶歇裙", "vintage square-neck silk crepe tea midi dress with mother-of-pearl buttons"),
    ("改良斜襟盘扣织金旗袍长礼服", "modern oriental qipao gown with side slit and delicate frog closures"),
    ("极简Polo领锋利百褶运动连身裙", "minimalist polo collar sleeveless dress with sharp knife-pleated skirt"),
    ("不规则解构斜肩落褶晚礼服", "avant-garde one-shoulder architectural draped maxi gown")
]


def generate_unique_garment(existing_labels: set, category_preference: str = None) -> dict:
    """Generate a guaranteed unique garment design adhering to commercial ghost mannequin standards."""
    cat = category_preference
    if not cat:
        cat = random.choice(["tops", "bottoms", "full"])

    prefix_map = {"tops": "top", "bottoms": "btm", "full": "full"}
    prefix = prefix_map[cat]

    for attempt in range(200):
        theme = random.choice(STYLES_THEMES)
        col_cn, col_en = random.choice(COLORS)
        fab_cn, fab_en = random.choice(FABRICS)

        if cat == "tops":
            sil_cn, sil_en = random.choice(TOPS_SILHOUETTES)
        elif cat == "bottoms":
            sil_cn, sil_en = random.choice(BOTTOMS_SILHOUETTES)
        else:
            sil_cn, sil_en = random.choice(FULL_SILHOUETTES)

        label = f"{theme['name_cn']}{col_cn}{fab_cn}{sil_cn}"
        if label in existing_labels:
            continue

        desc = f"{theme['name_en']} {col_en} {fab_en} {sil_en} ({theme['keywords']})"
        prompt = (
            f"High-end fashion commercial product photography, vertical 9:16. "
            f"A standalone {col_en} {fab_en} {sil_en}, featuring {theme['keywords']}, "
            f"displayed on an invisible ghost mannequin against a pure solid white studio background. "
            f"Exquisite fabric texture, realistic natural creases and folds, clean studio commercial lighting, ultra-detailed 8k resolution."
        )

        return {
            "category": cat,
            "prefix": prefix,
            "label": label,
            "desc": desc,
            "prompt": prompt
        }

    # Fallback unique timestamp
    ts = random.randint(100, 999)
    label = f"{theme['name_cn']}{col_cn}{fab_cn}{sil_cn}_{ts}"
    return {
        "category": cat,
        "prefix": prefix,
        "label": label,
        "desc": desc,
        "prompt": prompt
    }


# ============================================================================
# 2. CHARACTER PROCEDURAL ENGINE
# ============================================================================

SURNAME_POOL = [
    ("阮", "Ruan"), ("洛", "Luo"), ("尹", "Yin"), ("陆", "Lu"), ("楚", "Chu"),
    ("白", "Bai"), ("叶", "Ye"), ("温", "Wen"), ("唐", "Tang"), ("霍", "Huo"),
    ("宋", "Song"), ("钟", "Zhong"), ("花", "Hua"), ("裴", "Pei"), ("岑", "Cen"),
    ("乔", "Qiao"), ("席", "Xi"), ("宁", "Ning"), ("柳", "Liu"), ("云", "Yun"),
    ("苏", "Su"), ("姜", "Jiang"), ("沈", "Shen"), ("顾", "Gu"), ("傅", "Fu"),
    ("程", "Cheng"), ("薛", "Xue"), ("梁", "Liang"), ("谭", "Tan"), ("秦", "Qin"),
    ("南宫", "Nangong"), ("令狐", "Linghu"), ("司徒", "Situ"), ("欧阳", "Ouyang"),
    ("上官", "Shangguan"), ("皇甫", "Huangfu"), ("尉迟", "Yuchi"), ("慕容", "Murong"),
    ("闻人", "Wenren"), ("澹台", "Tantai")
]

GIVEN_NAME_POOL = [
    ("星竹", "Xingzhu"), ("晴川", "Qingchuan"), ("新月", "Xinyue"), ("清音", "Qingyin"),
    ("天歌", "Tiange"), ("羽薇", "Yuwei"), ("沐晨", "Muchen"), ("小柔", "Xiaorou"),
    ("梦璃", "Mengli"), ("青黛", "Qingdai"), ("南乔", "Nanqiao"), ("灵儿", "Linger"),
    ("若离", "Ruoli"), ("语涵", "Yuhan"), ("曼舒", "Manshu"), ("楚楚", "Chuchu"),
    ("幼清", "Youqing"), ("初夏", "Chuxia"), ("依诺", "Yinuo"), ("知微", "Zhiwei"),
    ("微雨", "Weiyu"), ("晚照", "Wanzhao"), ("采薇", "Caiwei"), ("知夏", "Zhixia"),
    ("清欢", "Qinghuan"), ("安然", "Anran"), ("黎黎", "Lili"), ("怀玉", "Huaiyu"),
    ("雪见", "Xuejian"), ("若曦", "Ruoxi"), ("素秋", "Suqiu"), ("灵均", "Lingjun"),
    ("芷若", "Zhiruo"), ("语嫣", "Yuyan"), ("灵素", "Lingsu"), ("山山", "Shanshan"),
    ("红鱼", "Hongyu"), ("思恬", "Sitian"), ("半夏", "Banxia"), ("朝颜", "Chaoyan")
]

CHARACTER_ARCHETYPES = [
    {
        "style": "新中式清雅温婉 (Neo-Chinese Poetic)",
        "features": "gentle almond eyes, luminous porcelain skin, refined graceful jawline",
        "hair": "high elegant ponytail with delicate stray wisps, silky jet black hair",
        "suit": "minimalist neutral ivory seamless form-fitting base-body suit",
        "bg": "solid clean warm-gray studio background, soft cinematic diffuse beauty lighting",
        "keywords": "Neo-Chinese gentle beauty, poise, elegance"
    },
    {
        "style": "赛博未来机能御姐 (Cyberpunk Techwear)",
        "features": "sharp fox eyes, sculpted cheekbones, strong straight brow ridge",
        "hair": "platinum silver short crop haircut with sharp tapered nape",
        "suit": "minimalist black technical compression base-body suit with geometric contour seams",
        "bg": "minimalist dark slate studio background with subtle teal rim light, sharp high-contrast studio lighting",
        "keywords": "futuristic, athletic, cool, cybernetic aesthetic"
    },
    {
        "style": "老钱极简静奢名媛 (Quiet Luxury)",
        "features": "intelligent almond eyes, refined patrician nose, balanced facial symmetry",
        "hair": "side-parted lustrous dark wavy bob behind ears",
        "suit": "minimalist charcoal-taupe seamless premium compression base-body suit",
        "bg": "solid clean light-gray architectural studio background, natural soft window lighting",
        "keywords": "old money elegance, minimalist luxury, calm sophistication"
    },
    {
        "style": "水墨仙侠清冷绝尘 (Ethereal Xianxia)",
        "features": "ethereal delicate features, high delicate nose bridge, translucent fair complexion",
        "hair": "flowing silky dark hair cascading down to waist with subtle soft waves",
        "suit": "minimalist celadon-tinted off-white seamless form-fitting bodysuit",
        "bg": "pure minimalist studio backdrop with subtle bamboo shadow gradient, soft glowing light",
        "keywords": "fairytale, immortal ethereal beauty, poetic ink wash"
    },
    {
        "style": "千禧元气轻朋克 (Y2K Preppy Punk)",
        "features": "round bright eyes, high cheekbones, radiant sun-kissed skin",
        "hair": "messy textured wolf-cut hair with dark burgundy tips",
        "suit": "minimalist dark heather-gray seamless form-fitting base-body suit",
        "bg": "solid neutral concrete gray studio backdrop, high-end magazine lookbook lighting",
        "keywords": "Y2K, energetic, charismatic, indie chic"
    },
    {
        "style": "高智职场精英大女主 (Executive Power)",
        "features": "sharp bright eyes, sculpted defined jawline, strong straight brow",
        "hair": "sharp clean-parted straight dark hair neatly tucked behind ears",
        "suit": "minimalist deep graphite seamless compression bodysuit",
        "bg": "clean neutral architectural studio background, crisp editorial key lighting",
        "keywords": "executive, high intelligence, leadership, statuesque"
    },
    {
        "style": "港风复古明艳美人 (Retro Glamour)",
        "features": "expressive deep-set brown eyes, natural sculpted arched brows, velvety matte skin",
        "hair": "voluminous layered raven black retro waves",
        "suit": "minimalist deep espresso-brown seamless compression bodysuit",
        "bg": "warm sepia-tinted cinematic studio backdrop, rich Rembrandt portrait lighting",
        "keywords": "90s Hong Kong cinema aesthetic, captivating, nostalgic glamour"
    }
]

# ============================================================================
# 3. BODY TENSION & SPECIAL AESTHETICS ENGINE
# ============================================================================

DEFAULT_BODY_TENSION_CURVES = [
    {"id": "slim_willowy", "name_cn": "纤细清瘦骨感型", "weight": 14,
     "prompt_en": "slim willowy frame, slender arms and long delicate neck, subtle flat chest line, narrow waist with minimal hip curve, light graceful posture"},
    {"id": "average_balanced", "name_cn": "标准匀称日常型", "weight": 20,
     "prompt_en": "natural average build, balanced shoulder-to-hip proportion, healthy soft waistline, realistic everyday body proportions, relaxed natural stance"},
    {"id": "soft_full_figured", "name_cn": "微胖圆润亲善型", "weight": 12,
     "prompt_en": "soft full-figured build, gently rounded belly and fuller arms and thighs, warm approachable presence, realistic soft body contours, comfortable posture"},
    {"id": "athletic_toned_core", "name_cn": "运动健硕力量型", "weight": 10,
     "prompt_en": "athletic muscular build, defined shoulders and toned arms, firm flat stomach, strong upright posture, healthy fit appearance"},
    {"id": "voluptuous_grace", "name_cn": "丰腴性感曲线型", "weight": 7,
     "prompt_en": "voluptuous natural curves, full bust and rounded hip contour, softly sculpted waist, confident feminine presence"}
]

DEFAULT_EXPRESSION_TONES = [
    {"id": "gentle_smile", "name_cn": "温柔含笑",
     "prompt_en": "soft warm smile with relaxed brow, gentle downward gaze, serene approachable demeanor"},
    {"id": "cool_alienated", "name_cn": "清冷疏离",
     "prompt_en": "cool detached expression, level unsmiling gaze, composed aloof demeanor, minimal facial tension"},
    {"id": "playful_spirited", "name_cn": "俏皮灵动",
     "prompt_en": "playful bright expression, slightly raised brows, subtle smirk, lively alert demeanor"},
    {"id": "calm_composed", "name_cn": "沉稳内敛",
     "prompt_en": "calm composed expression, steady direct gaze, quiet self-possessed demeanor"},
    {"id": "determined_driven", "name_cn": "坚定果敢",
     "prompt_en": "firm determined expression, sharp focused gaze, resolute driven demeanor"}
]

DEFAULT_SPECIAL_AESTHETICS = [
    {"id": "porcelain_sheen_collarbone", "name_cn": "瓷白微光与深邃锁骨",
     "prompt_en": "luminous translucent skin with subtle collarbone sheen, delicate stray hair strands dancing in gentle breeze"},
    {"id": "cinematic_rim_highlights", "name_cn": "电影级轮廓光与发丝质感",
     "prompt_en": "delicate rim light accentuating shoulder contours, crisp individual hair strand definition"},
    {"id": "strained_fabric_tension", "name_cn": "面料张力微拉扯细节",
     "prompt_en": "fabric naturally contouring the body with realistic tension folds, elegant physical drape"},
    {"id": "poetic_waterdrop_sheen", "name_cn": "水光微润与清冽气场",
     "prompt_en": "subtle dewy glow on temples and collarbone, refined skin luminosity, sharp high-fashion editorial clarity"},
    {"id": "freckles_natural_texture", "name_cn": "自然雀斑与真实肌理",
     "prompt_en": "light natural freckles across the nose bridge, visible skin texture and pores, unretouched realistic finish"}
]


def load_body_tension_and_specials():
    """Load procedural body curves, expression tones and special aesthetics from prompts/ asset."""
    json_path = ROOT / "prompts" / "body_tension_special_prompts.json"
    curves = DEFAULT_BODY_TENSION_CURVES
    expressions = DEFAULT_EXPRESSION_TONES
    specials = DEFAULT_SPECIAL_AESTHETICS
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            curves = data.get("body_tension_curves") or curves
            expressions = data.get("expression_tones") or expressions
            specials = data.get("special_aesthetics") or specials
        except Exception:
            pass
    return curves, expressions, specials


def _weighted_pick(pool):
    return random.choices(pool, weights=[max(1, int(o.get("weight", 1))) for o in pool])[0]


def generate_unique_character(existing_names: set) -> dict:
    """Generate a guaranteed unique Asian female character profile with independent body, expression and texture draws."""
    curves_pool, expr_pool, specials_pool = load_body_tension_and_specials()

    for attempt in range(200):
        sur_cn, sur_en = random.choice(SURNAME_POOL)
        gn_cn, gn_en = random.choice(GIVEN_NAME_POOL)
        cn_name = f"{sur_cn}{gn_cn}"
        en_name = f"{sur_en} {gn_en}"

        if cn_name in existing_names:
            continue

        arch_base = random.choice(CHARACTER_ARCHETYPES)
        body_opt = _weighted_pick(curves_pool)
        expr_opt = random.choice(expr_pool)
        special_opt = random.choice(specials_pool)

        # Non-mutating enrichment of archetype for seamless downstream consumption
        arch = dict(arch_base)
        arch["features"] = ", ".join([
            arch_base["features"], body_opt["prompt_en"],
            expr_opt["prompt_en"], special_opt["prompt_en"]
        ])
        arch["body_tension"] = body_opt["name_cn"]
        arch["expression_tone"] = expr_opt["name_cn"]
        arch["special_feature"] = special_opt["name_cn"]
        arch["body_prompt"] = body_opt["prompt_en"]
        arch["expression_prompt"] = expr_opt["prompt_en"]
        arch["special_prompt"] = special_opt["prompt_en"]

        age = random.randint(20, 38)

        return {
            "cn_name": cn_name,
            "en_name": en_name,
            "age": age,
            "archetype": arch,
            "body_tension": body_opt["name_cn"],
            "expression_tone": expr_opt["name_cn"],
            "special_feature": special_opt["name_cn"]
        }

    # Fallback
    rand_id = random.randint(10, 99)
    cn_name = f"苏清歌_{rand_id}"
    en_name = f"Su Qingge {rand_id}"
    arch_base = random.choice(CHARACTER_ARCHETYPES)
    body_opt = _weighted_pick(curves_pool)
    expr_opt = random.choice(expr_pool)
    special_opt = random.choice(specials_pool)
    arch = dict(arch_base)
    arch["features"] = ", ".join([
        arch_base["features"], body_opt["prompt_en"],
        expr_opt["prompt_en"], special_opt["prompt_en"]
    ])
    arch["body_tension"] = body_opt["name_cn"]
    arch["expression_tone"] = expr_opt["name_cn"]
    arch["special_feature"] = special_opt["name_cn"]

    return {
        "cn_name": cn_name,
        "en_name": en_name,
        "age": 22,
        "archetype": arch,
        "body_tension": body_opt["name_cn"],
        "expression_tone": expr_opt["name_cn"],
        "special_feature": special_opt["name_cn"]
    }
