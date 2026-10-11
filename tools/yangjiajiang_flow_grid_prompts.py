#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · Flow 九宫格生成提示词模块（EP01《北汉风雪》/ EP05《误卯牌》/ EP06《李陵碑·殉国》/ EP07《七郎之死》）

用途：
1. 为第 1、5、6、7 集各 6 组 3x3 九宫格分镜总览板提供英文提示词。
2. 每组九宫格对应 9 镜（组 g 对应镜头 (g-1)*9+1 ~ g*9），逐 panel 与该组 9 镜剧情一一对应。

美术纪律（与元数据表一致）：
- 新白描 = 上美影手绘动画风：白描为骨 + 宣纸底 + 淡彩平涂。
- STYLE_BASE 与 GRID_HEAD 直接复用 EP04 flow_pilot 同名字符串，保持风格一致。
- EP01 / EP05 一律不启用朱砂红；EP06 为全片朱砂三处之一，仅撞碑一镜允许「黑白与一点朱砂」。
- 战场不给血（甲片崩开 / 兵刃脱手 / 倒旗 / 攥紧的手 侧写）；EP06 七郎遇害完全不拍（云过月）。
- EP07 一律不启用朱砂红（全片朱砂仅三处：第2集/第6集/第23集）；七郎遗身只写「甲片上密密箭孔」不给脸，棍打潘容「棍光一闪人落马」，全片没有一滴红。
- 人物脱敏：遵守 Flow/Veo Prominent People Policy，英文提示词严禁出现真实历史人名，
  一律改用「职能身份 + 宋代服饰 + 神态动作」等价描述。
"""

# 统一样式基座（正向描述，不使用否定句——Flow 无负向词字段）—— 与 EP04 完全一致
STYLE_BASE = (
    "Traditional Chinese ink-wash cut-paper animation style, vintage Shanghai Animation Film Studio aesthetic, "
    "crisp black ink brush outlines, flat solid blocks of mineral pigment colour, raw rice paper texture, "
    "palette of ink black, moon white, celadon green, ochre and pale gold, flat cel-shaded light, film grain."
)

GRID_HEAD = (
    "A 3x3 nine-panel cinematic storyboard grid, panels read left to right top to bottom, "
    "nine consecutive scenes from a Northern Song Dynasty historical epic. "
    "Each panel is full-bleed artwork filling its own cell edge to edge, "
    "clean illustration only with no panel numbers, no captions and no text of any kind. "
)

# 通用人物等价描述（脱敏，严禁真实历史人名）
_YANG = "a veteran Song general with iron lamellar armour and a grey beard"
_EMPRESS = "a stern matriarch in a green cloak"
_RULER = "a local lord in a plain dark robe"
_EMPEROR = "an emperor in a golden dragon robe"
_MINISTER = "a scheming senior court minister in dark brocade official robes"
_VANGUARD = "an armoured vanguard general"
_OFFICIAL = "a court official in plain robes"
_BURLY = "a burly bearded veteran general in iron armour"
_ADVISOR = "a lean pale advisor in a grey robe"
_PRINCE = "a young prince in a pale travelling robe"
_ENEMY_CMD = "an enemy commander in dark lamellar armour"
_ENEMY_QUEEN = "a regal enemy queen in ornate dark robes"
_SON = "the young armoured eldest son"
_SIXTH = "the steady young armoured sixth son"
_SEVENTH = "the hot-blooded young armoured seventh son"
_ALLY = "a loyal allied general in worn armour"
_OLD_SOLDIER = "a dust-covered old soldier"
_MONK = "a tall monk with a shaven head and a still face in a plain grey robe"
_NEPHEW = "the minister's nephew, a sneering young officer in a fine cloak"
_CUDGEL = "a stout loyal warrior swinging an iron cudgel"
_FISHERS = "two weathered soldiers dressed as fishermen"

# 24 × 6 组九宫格提示词：EP01/EP05/EP06/EP07 各 6 组，每组严格 9 个 panel
EP_GRID_PROMPTS = {
    1: {
        1: GRID_HEAD + (
            "Panel 1: a snow-covered northern frontier wall beneath heavy leaden clouds, beacons standing empty. "
            "Panel 2: inside a headquarters hall, a family of nine seated in two ranks, " + _YANG + " seated at the centre with no weapon in hand. "
            "Panel 3: " + _EMPRESS + " beside the steps as seven armoured sons enter one by one, each in a different armour colour. "
            "Panel 4: close on a desk with scrolls of military books and a map, the grey-bearded general pressing a finger on the chart. "
            "Panel 5: " + _RULER + " pushing a small wooden seal slowly across the desk. "
            "Panel 6: the grey-bearded general receiving the seal in both hands, head lowered, silent. "
            "Panel 7: " + _RULER + " gazing steadily at the general, hall attendants standing with hands clasped. "
            "Panel 8: the grey-bearded general in armour stepping out of the mansion holding a golden glaive, two sons following through snow. "
            "Panel 9: a lone ochre war banner straining in the north wind above the frozen city wall. "
        ) + STYLE_BASE,
        2: GRID_HEAD + (
            "Panel 1: a vast enemy encampment of ochre tents spreading to the horizon, dust light drifting. "
            "Panel 2: inside a court hall, an official receiving a commission scroll, two fresh-armoured officers standing below the steps. "
            "Panel 3: a courtier stepping forward and pointing north, all eyes turning with his hand. "
            "Panel 4: the grey-bearded general and another officer riding in a tight column through snow, a lone rider breaking away. "
            "Panel 5: a short reply note landing in an open palm, then a map unrolled on a desk with a finger marking two points. "
            "Panel 6: the grey-bearded general reading the note with a faint smile, two cavalry columns leaving through a camp gate watched by a cloaked matriarch. "
            "Panel 7: two armies colliding along a snow plain, dust bursting up, blades flashing in a wall of motion. "
            "Panel 8: an emperor chasing on horseback as the general turns and looses an arrow, his horse rearing to catch the arrow in its teeth, the emperor thrown down. "
            "Panel 9: the grey-bearded general spear-tossing a brocade-robed minister off his horse, the minister lifting his dirty face in the mud, two banners cutting the enemy column apart. "
        ) + STYLE_BASE,
        3: GRID_HEAD + (
            "Panel 1: night, sparse lanterns among army tents, " + _EMPEROR + " standing with hands behind his back before a tent. "
            "Panel 2: inside a tent by lamplight, the grey-bearded general reporting, the local lord shown only as a dark back. "
            "Panel 3: close overhead of a fingertip drawing a circle on a map, a cannon mark on the line outside, emptiness inside. "
            "Panel 4: armoured soldiers creeping low through night mist toward a silent camp, faint light on their armour. "
            "Panel 5: a blinding white flash bursting from the centre of the dark camp, figures reduced to silhouettes. "
            "Panel 6: two columns of friendly soldiers colliding blind in smoke and dust, banners alike yet blades crossing. "
            "Panel 7: a cannon flash, the grey-bearded general's troops pouring down from two flanks onto a broken camp, dust everywhere. "
            "Panel 8: a kneeling armoured general reporting by a brazier, mud still crusted on his armour. "
            "Panel 9: the emperor lifting his face to a vast starry night sky, wide empty space above. "
        ) + STYLE_BASE,
        4: GRID_HEAD + (
            "Panel 1: endless grey drizzle over a camp, water pooling outside the tents under a low sky. "
            "Panel 2: the grey-bearded general standing at a tent opening, watching the rain, cloak heavy with damp. "
            "Panel 3: soldiers carrying firewood down a wet hillside, dry wood stacked into a mountain inside the camp. "
            "Panel 4: night, the emperor and officers outside a tent studying the sky, clouds hiding every star, one stamping a boot. "
            "Panel 5: close, shivering soldiers crouched under bare dripping trees, tunics soaked, only wet backs visible. "
            "Panel 6: the grey-bearded general pointing to two slopes, dispatching his sons into the rain. "
            "Panel 7: a low vertical view of two hidden ranks of archers along snowy left and right ridges, utterly still. "
            "Panel 8: a signal cannon bursting through the rain as troops rush a camp and both ridge lines rise together, arrows mixing with rain. "
            "Panel 9: a broken camp, banners fallen and saddles empty in grey rain and dust, no blood anywhere. "
        ) + STYLE_BASE,
        5: GRID_HEAD + (
            "Panel 1: inside a tent, courtiers standing with clasped hands, the emperor pacing restlessly, one official stepping forward. "
            "Panel 2: close on a court official pleading earnestly, candlelight lighting only half his face. "
            "Panel 3: close push-in on the emperor's clenched hand on the desk slowly uncurling finger by finger. "
            "Panel 4: " + _RULER + " pressing a jade seal down onto a peace document, attendants holding their breath. "
            "Panel 5: a dim bedchamber at night, one lone candle casting a small warm circle, the couch lost in shadow. "
            "Panel 6: a thin aged hand reaching trembling out from behind a bed curtain, the face never shown. "
            "Panel 7: a rolled imperial testament passing from the old hand into a younger firm hand, the two hands overlapping. "
            "Panel 8: the testament unrolled, silk carrying steady brushstrokes, camera moving along the lines. "
            "Panel 9: a young successor kneeling before the couch, both hands raising the testament, a single candle beam on it. "
        ) + STYLE_BASE,
        6: GRID_HEAD + (
            "Panel 1: dawn, an ocean of ochre-gold war banners unfolding across the plain, golden light along the edges. "
            "Panel 2: ranks of troops extending into morning mist, armour and banners merging into one long line. "
            "Panel 3: a courier taking a sealed edict from a desk and swinging up onto his horse, robe flaring. "
            "Panel 4: a single rider galloping away into the snowy horizon, hoofprints winding, figure shrinking small. "
            "Panel 5: a lone old mountain pass standing in morning mist, a line of beacons fading into the distance. "
            "Panel 6: a distant walled frontier town taking shape out of the snow plain, a banner lifting on its wall. "
            "Panel 7: close, a rolled edict opening slowly in a palm, camera locked, brushstrokes clear in side light. "
            "Panel 8: close glide along the edict's final line toward its signature, ink dark against raw paper. "
            "Panel 9: sunrise spreading a golden line along the horizon over a long empty snow road, dust hanging, closing vista. "
        ) + STYLE_BASE,
    },
    5: {
        1: GRID_HEAD + (
            "Panel 1: an enemy court hall, " + _ENEMY_QUEEN + " seated high, counting rods laid out one by one on the table, armoured officers around. "
            "Panel 2: an enemy commander in lamellar armour receiving command, tents and banners spreading beyond the tent flap. "
            "Panel 3: a Song court hall, " + _MINISTER + " receiving a marshal's commission, set half a head lower among the ranks. "
            "Panel 4: close, " + _ADVISOR + " leaning in to whisper to the marshal, a finger pointing forward, a cold glint in the marshal's eye. "
            "Panel 5: " + _PRINCE + " stepping forward, brow furrowed, wary eyes on the marshal. "
            "Panel 6: the young prince raising his tablet to petition, the emperor giving a slight nod, courtiers glancing at one another. "
            "Panel 7: a rolled edict being sealed and handed to a courier striding out through morning light at the hall gate. "
            "Panel 8: " + _EMPRESS + " standing beneath a lamp, needlework paused, brow faintly knotted with worry. "
            "Panel 9: " + _YANG + " quietly reassuring his wife, his gaze fixed on the distance, never meeting her eyes, a hand on his sword. "
        ) + STYLE_BASE,
        2: GRID_HEAD + (
            "Panel 1: a bleak frontier plain with two camps facing east and west, banners curling in the cold wind. "
            "Panel 2: high overhead view of a west camp and an east camp separated by an empty strip, each with its own tall banner. "
            "Panel 3: close, " + _ADVISOR + " beside the marshal making a push-forward gesture with his hand, calculation in his eyes. "
            "Panel 4: " + _BURLY + " clasping his fist and answering boldly, hair and beard stirring in the wind, wholly unaware. "
            "Panel 5: two horsemen charging toward each other on open ground, spear shadows overlapping, dust rising. "
            "Panel 6: two riders traded blows across a dust-filled field, sparks flickering in the grey haze. "
            "Panel 7: a cannon burst tearing open the frame as a column of riders pours from the treeline, cutting off the road back. "
            "Panel 8: the burly general alone between two enemy bodies, spears closing in from all sides, armour disarrayed but unshaken. "
            "Panel 9: several riders in armour bursting through dust, a single sweeping glaive strike sending an enemy weapon flying from his hand, no blood shown. "
        ) + STYLE_BASE,
        3: GRID_HEAD + (
            "Panel 1: close, " + _ADVISOR + " whispering to the marshal, a finger on the muster ledger, smiles cold in the lamplight. "
            "Panel 2: officers drawn up before a tent as a herald calls a name three times into the hush, no one answering. "
            "Panel 3: close push-in on a wooden penalty tablet hung before the tent, a banner shadow sweeping slowly across its face. "
            "Panel 4: the grey-bearded general arriving and glaring up at the tablet, beard bristling, fists clenched. "
            "Panel 5: " + _MINISTER + " seated behind the desk waving a hand outward, eyes turned away, officers exchanging glances. "
            "Panel 6: two soldiers stepping up to seize the general by the arms, his head held high in the tent doorway. "
            "Panel 7: a young hot-blooded officer half-drawing his sword, eyes blazing, body leaning forward. "
            "Panel 8: the eldest son catching the young officer's wrist and shaking his head, whispering urgently, gaze toward the tent beyond. "
            "Panel 9: a burly bearded general stooping to untie the ropes from the grey-bearded general's arms, the coils falling to the ground. "
        ) + STYLE_BASE,
        4: GRID_HEAD + (
            "Panel 1: close, " + _ADVISOR + " standing sideways in the tent proposing a distant errand, a hidden smile at the corner of his eye. "
            "Panel 2: " + _MINISTER + " standing at the desk handing out a sealed order, the burly general receiving it with clasped hands. "
            "Panel 3: the burly general alone at the camp gate, one hand on his saddle, hesitating, his shadow stretched long. "
            "Panel 4: the burly general glancing back toward the west camp, a lone banner standing quiet in the dusk. "
            "Panel 5: the grey-bearded general striding up and clapping the burly general firmly on the shoulder, the two meeting eyes. "
            "Panel 6: close on two weathered hands gripping each other tightly, dusk light on the knuckles, one hand trembling. "
            "Panel 7: the burly general swinging onto his horse and riding out of the gate, dust trailing, shrinking into the dusk. "
            "Panel 8: the grey-bearded general standing alone outside the gate watching the road, cloak flaring in the wind, utterly still. "
            "Panel 9: dusk settling over a quiet camp, one lone banner curling in the evening wind. "
        ) + STYLE_BASE,
        5: GRID_HEAD + (
            "Panel 1: inside a tent, the grey-bearded general and officers gathered around a map spread on the desk, a finger tracing slowly. "
            "Panel 2: close overhead of a freshly written challenge letter still wet with ink, a palm pressing it down. "
            "Panel 3: a courier striding out of the camp holding the letter, then swinging up and away, gate banners sweeping past. "
            "Panel 4: dim interior of an enemy tent, " + _ENEMY_CMD + " reading and then setting his brush hard upon a reply, a brazier flickering. "
            "Panel 5: the enemy commander gesturing at a gorge on the map, an officer taking the order, firelight casting a cold edge. "
            "Panel 6: wide high-angle view of a deep empty gorge stretching away, faint armour light hidden along both high walls. "
            "Panel 7: the grey-bearded general clasping his hands before the tent pleading his case, sons ranked behind him, candles still. "
            "Panel 8: " + _MINISTER + " turning his back and flicking his sleeve, face gloomy, ignoring the plea entirely. "
            "Panel 9: dusk in the gorge, banner-tips quietly rising along both high walls, the mouth of the valley dark as a gaping jaw. "
        ) + STYLE_BASE,
        6: GRID_HEAD + (
            "Panel 1: low angle on " + _MINISTER + " waving an order down from behind the desk, soldiers stirring, officers silent. "
            "Panel 2: two soldiers raising heavy punishment staves, the staves sweeping arcs in the tent light, no faces below. "
            "Panel 3: close on a punishment staff striking down again and again while a single fist clenches white and rigid beside it, no blood anywhere. "
            "Panel 4: the grey-bearded general bent over the frame, yet his spine held dead straight, officers watching sidelong in silence. "
            "Panel 5: outside the tent curtain, a young officer straining to rush in while the eldest son holds him back and shakes his head. "
            "Panel 6: the grey-bearded general straightening up and speaking plainly, head high, no fear in his eyes. "
            "Panel 7: the general standing with clasped hands pleading his case in the tent, candlelight on half his face, officers moved yet silent. "
            "Panel 8: " + _MINISTER + " turning slowly from his back to a half profile, one side of his face emerging in the light. "
            "Panel 9: extreme close on the marshal's mouth curling into the faintest cold smile, one glint in his eye, everything frozen quiet. "
        ) + STYLE_BASE,
    },
    6: {
        1: GRID_HEAD + (
            "Panel 1: inside a marshal tent, " + _YANG + " clasping his fists in a stiff bow, enduring hidden pain. "
            "Panel 2: close on a gorge map spread on the desk, a finger tracing where crossbowmen should wait. "
            "Panel 3: " + _MINISTER + " nodding agreement, standing half a head lower, eyes drifting off-frame. "
            "Panel 4: close on " + _YANG + " walking with a slight stumble, waving off concern with a faint smile. "
            "Panel 5: " + _SIXTH + " clasping his fists, pleading that the enemy's strength is still unknown. "
            "Panel 6: a column of allied riders entering the camp gate, " + _ALLY + " dismounting and saluting. "
            "Panel 7: close on two gauntleted hands gripping each other firmly in the last light. "
            "Panel 8: wide high-angle view of enemy soldiers pouring over ridgelines, banners blotting the sky. "
            "Panel 9: " + _SEVENTH + " asking to lead the vanguard, then swinging onto his horse. "
        ) + STYLE_BASE,
        2: GRID_HEAD + (
            "Panel 1: " + _SEVENTH + " charging alone into an enemy formation, snow dust swirling around his spear. "
            "Panel 2: a quick clash, an enemy rider's weapon flying loose as he tumbles from the saddle, no blood. "
            "Panel 3: a gorge stockade collapsing as a Song banner rises over the first pass. "
            "Panel 4: " + _YANG + " noting merit on a board, then pointing his whip toward a second gorge. "
            "Panel 5: a blinding white flash bursting over the second pass, enemy figures tumbling out of the glare. "
            "Panel 6: an enemy commander wheeling his horse and fleeing, riders and banners collapsing behind. "
            "Panel 7: " + _YANG + " reining in on a ridge, hand raised to halt the whole column. "
            "Panel 8: close, the general quietly ordering his youngest son to ride back for reinforcements. "
            "Panel 9: a worn leather wine flask tossed through the air into the young man's hands, snow dust kicked up as he rides off. "
        ) + STYLE_BASE,
        3: GRID_HEAD + (
            "Panel 1: an enemy column bursting from a side valley, spears sealing the mouth of the pass. "
            "Panel 2: wide view of a Song column trapped between enemy banners front and rear. "
            "Panel 3: wide high-angle deep view down a gorge filled with falling arrows, arrows only, no figures. "
            "Panel 4: an axe-blade flash, armour plates scattering, " + _ALLY + " tumbling from his horse, no blood. "
            "Panel 5: " + _SIXTH + " chasing an enemy horseman along a snowy track, spear levelled. "
            "Panel 6: the young rider wrenching his horse around, distant riders closing around a familiar armoured figure. "
            "Panel 7: enemy heavy riders slicing a wedge across the valley, cutting the Song force in two. "
            "Panel 8: the young rider's own view, fog drifting across the gorge, only blurred banner shapes beyond. "
            "Panel 9: " + _YANG + " fighting a rearguard among thinning silhouettes in dust. "
        ) + STYLE_BASE,
        4: GRID_HEAD + (
            "Panel 1: dusk over a quiet gorge, a handful of survivors gathering, few banners left standing. "
            "Panel 2: " + _YANG + " leaning on his planted golden glaive, shoulders rising and falling. "
            "Panel 3: wide deep view of a hundred soldiers kneeling in rows on the snow, utterly still. "
            "Panel 4: " + _OLD_SOLDIER + " kneeling and crying out his vow, faces bowed behind him. "
            "Panel 5: the general raising the old soldier up by the arm, eyes moving across each dusty face. "
            "Panel 6: the general swinging onto his horse and lifting the golden glaive into the last light. "
            "Panel 7: the hundred riders charging again, blades and spears churning through snow dust. "
            "Panel 8: ranks of enemy banners toppling over in retreat, no figures struck, no blood. "
            "Panel 9: high-angle deep view of empty saddles standing and fallen banners half-buried in dusk snow. "
        ) + STYLE_BASE,
        5: GRID_HEAD + (
            "Panel 1: " + _YANG + ", exhausted and wounded, climbing a low mound beside his horse. "
            "Panel 2: following his gaze downward, a weather-worn stone tablet tilted in the frozen earth. "
            "Panel 3: a bare willow beside the tablet, every branch snapped short, reaching skyward. "
            "Panel 4: vertical glide down the weathered tablet face, eroded carved grooves standing out in raking light. "
            "Panel 5: the general looking around at his remaining men, speaking low and steady for the last time. "
            "Panel 6: unhurried close gestures, fastening the last armour plate, smoothing his beard, folding his torn cloak at the tablet's base, planting the golden glaive beside it. "
            "Panel 7: camera rising slowly behind the general's shoulders toward the tablet as he steps forward three times and bows his head against the stone, all colour draining away to pure black-and-white ink with a single touch of cinnabar red. "
            "Panel 8: wide still view of an empty snowy field, snow falling on scattered blades and fallen banners, no figures. "
            "Panel 9: pure black frame, wind alone filling the darkness. "
        ) + STYLE_BASE,
        6: GRID_HEAD + (
            "Panel 1: night, tent flaps closed tight, " + _MINISTER + " drinking alone under a lone lamp, spearmen guarding outside. "
            "Panel 2: " + _SEVENTH + " snow-covered, drawing his sword and bursting through the tent doorway past halberds. "
            "Panel 3: shot framing only his shoulders, snow falling from his armour, fists clenching as he pleads. "
            "Panel 4: the minister giving a single glance, soldiers swarming to bind the young man's arms with rope. "
            "Panel 5: vertical glide across the faces of surrounding soldiers, each lowering his eyes with tears. "
            "Panel 6: high-angle view of night clouds crossing the moon, the rim of light dimming once, no figures at all. "
            "Panel 7: an ownerless horse with an empty saddle standing outside a camp gate at night, snow settling on the saddle, loose reins hanging to the ground. "
            "Panel 8: wide view of a great army camp at night, lanterns going out one by one, a single tent lamp still burning. "
            "Panel 9: dawn over a mountain gorge, thousands of arrows standing upright in snow like a forest, two tattered banners motionless, the snowfall ceasing. "
        ) + STYLE_BASE,
    },
    7: {
        1: GRID_HEAD + (
            "Panel 1: night reeds, two weathered soldiers dressed as fishermen stepping out of a reed bank, alert and wary. "
            "Panel 2: far view of the body of a young armoured soldier drifting downstream on grey water, half-sunk and silent. "
            "Panel 3: extreme close vertical glide along armour plates pierced with dense arrow-holes, the face never shown. "
            "Panel 4: the two soldiers kneeling on the bank weeping out loud, reed leaves trembling around them. "
            "Panel 5: " + _SIXTH + " stumbling toward them along a foggy bank, unmelted snow still on his armour. "
            "Panel 6: the young general gripping the body's shoulders, frozen still in the shallow water. "
            "Panel 7: close on his clenched fists and lowered head, vowing through gritted teeth. "
            "Panel 8: the three of them digging into frozen ground by the river, sods turning over slowly. "
            "Panel 9: close on a worn leather wine flask hung on a bare branch above a small grave mound. "
        ) + STYLE_BASE,
        2: GRID_HEAD + (
            "Panel 1: morning mist over a low mound, the young general walking up it with heavy slow steps. "
            "Panel 2: an old general lying still in the snow, broken armour barely visible beneath the frost. "
            "Panel 3: slow lateral glide across torn lamellar plates scored with old scars. "
            "Panel 4: extreme close on a worn gilt belt buckle, a trembling hand hovering above it. "
            "Panel 5: the young general collapsing to his knees in the snow. "
            "Panel 6: overhead view of him digging the frozen soil bare-handed, earth piling up beside him. "
            "Panel 7: close on a broken halberd planted slantwise on the grave, its tassel frozen stiff. "
            "Panel 8: close, his hand closing on a golden glaive planted beside a stone tablet and drawing it out slowly. "
            "Panel 9: near view of his face turned toward the distant enemy camp, eyes like spent coals. "
        ) + STYLE_BASE,
        3: GRID_HEAD + (
            "Panel 1: the young general lunging with a spear into a knot of enemy riders. "
            "Panel 2: wide view of enemy riders closing into a full ring around a lone figure. "
            "Panel 3: circling view of a worn rider fending off spear shadows from all sides. "
            "Panel 4: armour plates bursting loose as he shoulders free, no blood shown anywhere. "
            "Panel 5: ranks of enemy banners toppling backward as leaderless riders scatter into the snow. "
            "Panel 6: wide high-angle deep view of snow falling evenly on two fresh grave mounds. "
            "Panel 7: a lone rider heading south through a wind-blown snowfield, shrinking small. "
            "Panel 8: a monastery veiled in mountain cloud, stillness implying a far bell. "
            "Panel 9: the young general beneath a monastery gate, a grey-robed attendant gesturing him inside. "
        ) + STYLE_BASE,
        4: GRID_HEAD + (
            "Panel 1: inside a monk's cell, one small lamp, the young general speaking low with head bowed. "
            "Panel 2: close on " + _MONK + " listening with eyes closed, thin incense smoke rising by a Buddha niche. "
            "Panel 3: the two brothers embracing, both shaking with silent grief. "
            "Panel 4: the monk rising and lifting a heavy iron staff from the corner of the cell. "
            "Panel 5: the young general stepping in to bar his way, hands open, head shaking. "
            "Panel 6: extreme close, the monk's fingers releasing the iron staff one knuckle at a time, the staff leaning back against the wall. "
            "Panel 7: plain cloth clothes folded and offered, the monk fastening his brother's belt with slow care. "
            "Panel 8: close on two hands gripping each other, neither willing to let go first. "
            "Panel 9: far view from the monastery gate, a traveller growing smaller down the mountain path, the monk standing motionless. "
        ) + STYLE_BASE,
        5: GRID_HEAD + (
            "Panel 1: a Song court hall in uproar, ministers stepping forward to demand accountability. "
            "Panel 2: the emperor seated behind his desk, a raised hand hanging undropped between two memorials. "
            "Panel 3: night, " + _MINISTER + " whispering close to " + _NEPHEW + " beside a candle. "
            "Panel 4: vertical glide along a long silent queue at a sealed river ferry, guards checking every traveller. "
            "Panel 5: " + _NEPHEW + " ushering the young general aboard with a broad servile smile. "
            "Panel 6: aboard the boat, close on hidden blades half-drawn in every sleeve, the young general's eyes narrowing. "
            "Panel 7: a blinding white flash as he leaps for the shore, spray bursting, a figure sprinting away. "
            "Panel 8: a fishing boat calling from the reeds, two weathered fishermen waving him close. "
            "Panel 9: a cudgel sweeping in from off-frame, " + _NEPHEW + " tumbling from his horse, no blood shown. "
        ) + STYLE_BASE,
        6: GRID_HEAD + (
            "Panel 1: the young general clasping fists in farewell to two fishermen on a riverbank. "
            "Panel 2: close on a slander memorial being sealed by lamplight, a courier mounting in the dark. "
            "Panel 3: a crowded capital street, market voices pointing and murmuring as a traveller passes with lowered head. "
            "Panel 4: near view of a paper window at night with a single trembling shadow cast upon it. "
            "Panel 5: inside a princely hall, " + _PRINCE + " listening with rising anger as the petition is told. "
            "Panel 6: " + _PRINCE + " in plain travelling clothes escorting his guest out through a side gate. "
            "Panel 7: tilted-up still of a ceremonial drum stand silent in the night, dust resting on the drumhead. "
            "Panel 8: palace guards leading the young general up the steps, hands offering a folded memorial to the throne. "
            "Panel 9: the emperor weighing two rival claims, commissioning an armoured court envoy, who whispers his plan to the burly general named acting marshal. "
        ) + STYLE_BASE,
    },
}

if __name__ == "__main__":
    # 自检：EP01 / EP05 / EP06 各 6 组，每组严格 9 个 panel
    for ep in (1, 5, 6, 7):
        groups = EP_GRID_PROMPTS[ep]
        assert set(groups.keys()) == {1, 2, 3, 4, 5, 6}, "EP%d 必须 6 组" % ep
        total_words = 0
        for g in range(1, 7):
            p = groups[g]
            assert p.count("Panel ") == 9, "EP%d Grid%d 必须 9 个 panel，当前 %d" % (ep, g, p.count("Panel "))
            assert p.startswith(GRID_HEAD), "EP%d Grid%d 必须以 GRID_HEAD 开头" % (ep, g)
            assert p.endswith(STYLE_BASE), "EP%d Grid%d 必须以 STYLE_BASE 结尾" % (ep, g)
            w = len(p.split())
            assert 180 <= w <= 320, "EP%d Grid%d 字数异常: %d" % (ep, g, w)
            total_words += w
            print("  EP%d grid%d  panels=9  words=%d" % (ep, g, w))
        print("  EP%d 合计 words=%d" % (ep, total_words))
    # 本模块朱砂纪律：cinnabar/red 全模块仅允许出现 1 处（EP06 grid5 panel7 撞碑）
    n_cinnabar = sum(p.lower().count("cinnabar") for v in EP_GRID_PROMPTS.values() for p in v.values())
    assert n_cinnabar == 1, "全模块 cinnabar 仅允许 1 处（EP06 撞碑 panel），当前 %d" % n_cinnabar
    print("  朱砂纪律: 全模块 cinnabar 出现 %d 处（仅 EP06 撞碑 panel）" % n_cinnabar)
    print("[OK] Flow 九宫格提示词自检通过：EP01/EP05/EP06/EP07 各 6 组 × 9 panel")
