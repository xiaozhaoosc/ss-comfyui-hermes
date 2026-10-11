# -*- coding: utf-8 -*-
"""试播集制作包：第1集41镜 + 第6集31镜，逐镜竖屏改写 + Flow 英文提示词。"""
import os, json, traceback
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
OUTH = os.path.join(BASE, r"动画改编方案\杨家将_试播集制作包.html")
OUTX = os.path.join(BASE, r"动画改编方案\杨家将_试播集切分表.xlsx")
LOG = os.path.join(BASE, r".workbuddy\_tmp\qc\pilot.log")

STYLE_A = ("Traditional hand-painted 2D animation, flat mineral-pigment colour blocks, "
           "visible brush outlines, film grain, vintage Shanghai Animation Film Studio manner.")

# (镜序, 原书页, 段长, 竖屏画面中文, 英文提示词, 是否改写)
E1 = [
("01","1-4",8,"竖屏三层竖接：下 1/3 地砖与九个人的长影；中 1/3 帅府后堂，一家九人按前中后分层——杨业居中前景，七子二女依次在后；上 1/3 是压着城墙的雪线。镜头自下而上摇起：先入画的是影子，再是人，最后停在天与雪线。",
 "Vertical shot, camera slowly tilts upward from flagstones to walls to a snow line. Nine figures stand in layered depth inside a northern frontier hall — the father centre-front, seven sons and two daughters receding behind. Above them a snow-covered city wall. " + STYLE_A + " SFX: low wind.", True),
("02","1-4",4,"九人不再横向依次入画，改为沿纵深一层层退出来：先是佘赛花，再七个儿子，再两个女儿。衣甲颜色一层一色，一眼能数清。",
 "Vertical shot, camera slowly pulls back along depth. Nine figures in brightly different armour recede into ranks one after another — wife, then seven sons, then two daughters. Three layers of depth, each colour readable at a glance. " + STYLE_A + " SFX: cloth and armour shifting.", True),
("03","1-5",4,"固定中景。木印在画面下部，两只手在中部，上方是空墙。印推过去时发出很轻的一声。",
 "Static medium shot. A wooden seal slides across a dark table toward a general's open hands — seal low in frame, hands in the centre, blank wall above. " + STYLE_A + " SFX: one soft knock of wood on wood.", False),
("04","—",4,"特写。双手合拢握住印，低头三秒。画面里没有脸，只有手与印。",
 "Close shot, static. A general's hands close around a wooden seal. He lowers his head and holds. Hands in the lower third, empty space above. " + STYLE_A + " SFX: faint wind, no music.", False),
("05","1-6",8,"升镜头。赭石色帐篷在下方两层铺开、向纵深退去；上方 2/3 是空白天空。",
 "Vertical shot, camera rises steadily. Rows of ochre army tents recede into blank distance across the lower third; empty sky fills the rest. " + STYLE_A + " SFX: distant armour and horses.", False),
("06","1-7",4,"三人立于石阶上，正面朝镜头；上方留空白。甲胄崭新。",
 "Static medium shot. Three officers in brand-new armour stand on a stone step facing camera, blank sky above them. " + STYLE_A + " SFX: none.", False),
("07","1-8",4,"杨光美抬手指向画外上方，手停在画面上部；刘钧的脸在下部，视线跟着手走。",
 "Static medium shot. A courtier raises one arm pointing off-frame; the ruler's gaze follows it. The pointing hand held high in the upper third, both faces low. " + STYLE_A + " SFX: fabric rustle.", False),
("08","1-9",4,"队伍不再横向通过，改为从画面下方走入、向深处去。队形是整的。",
 "Vertical shot, camera moves slowly upward along a marching column. A short but ordered column advances away from camera into depth, entering from the bottom of frame. Ochre plain below, blank sky above. " + STYLE_A + " SFX: hooves on dry ground.", True),
("09","1-10",4,"杨延定纵马径直朝画面深处跑，越跑越小，不回头。这是杨家第一个离开画面的人。",
 "Static medium shot. A young officer rides directly away from camera, shrinking toward a low horizon. He does not look back. " + STYLE_A + " SFX: hoofbeats receding.", False),
("10","1-11",4,"手在画面下部，回书落到掌心。文书很短，只看得见一行。",
 "Close shot, static. A folded reply is placed into an open palm; one line of writing visible. Hand in the lower third. " + STYLE_A + " SFX: paper.", False),
("11","1-13",4,"高角度沿纵深俯拍：镜头顺着地图由近及远推过去，一根手指点在两处标记上。竖幅被地图填满。",
 "High angle looking straight down, camera pushes slowly along the depth of a map spread on a table. A finger touches two marked points. The map fills the frame. " + STYLE_A + " SFX: paper sliding.", True),
("12","1-14",4,"近景。脸在中部，身后是空白。他看着回书忽然笑了——全剧第一次笑。",
 "Close shot, static. A bearded general looks at a folded note and smiles for the first time. His face in the centre third, blank sky behind. " + STYLE_A + " SFX: wind.", False),
("13","1-15",4,"两路队伍朝相反方向出营；佘夫人立在营门目送。上方留白，下方是土。",
 "Static medium shot. Two columns ride out of a gate in opposite directions; a woman stands in the gateway watching them go. Blank sky above, dust below. " + STYLE_A + " SFX: hooves, wind.", False),
("14","1-16",4,"两军对撞。竖屏里改成自下而上摇：先入画的是奔马的四蹄，再是人，最后是举起的旗。",
 "Vertical shot, camera tilts up from galloping hooves to riders to raised banners as two armies collide. One general charges the enemy commander; another is intercepted. " + STYLE_A + " SFX: shouts, hooves, steel.", True),
("15","1-17",8,"核心镜头。回身一箭——切到马首：坐骑骤然一跃，张嘴把箭衔住。人被掀落在地。镜头不动。",
 "Vertical shot, static. A general wheels his horse and looses an arrow — cut to the horse's head: it leaps and catches the arrow in its teeth; the rider is thrown. Camera holds. " + STYLE_A + " SFX: bowstring, a horse scream, a dull impact.", False),
("16","1-18",4,"手持晃动。刀与身体在画面里交错，只有三秒。",
 "Handheld, brief. A chaotic close melee, bodies and blades crossing the frame. Three seconds only. " + STYLE_A + " SFX: shouts, steel.", False),
("17","1-19",4,"杨业一枪挑落潘仁美，连看都不看他一眼，拍马追太祖。潘仁美压在画面下缘，比旁人矮半头。",
 "Vertical medium shot. A general's spear throws a minister from his horse; the general does not look down and rides on. The fallen man sits low in frame. " + STYLE_A + " SFX: impact, then hooves departing.", False),
("18","1-20",4,"特写。趴在泥里抬头，视线追着画面上方远去的背影。眼里没有愤怒，只有记账。",
 "Close shot, static. A man lies face down in mud and lifts his head, eyes tracking something off-frame above him. No anger — only accounting. " + STYLE_A + " SFX: wind, distant battle.", False),
("19","1-21",4,"两路伏兵从画面两侧合拢，把援兵切成两段。人很小，分前后两层。",
 "Vertical wide shot, static. Two ambush parties close from both sides, cutting a relief column in two. Figures small, layered in depth against blank sky. " + STYLE_A + " SFX: drums, shouts.", False),
("20","1-22",8,"夜景。几盏灯压在画面下部，将军背手立在帐前，很矮；上方 2/3 是纯黑的天。",
 "Vertical night shot, static. Sparse lantern light on a few tents across the lower third; a commander stands with hands behind his back before a tent, small in frame; black night above. " + STYLE_A + " SFX: crickets, wind.", False),
("21","1-23",4,"将军进帐。帐内那人的脸始终在画外——只看得见他的背影与肩。",
 "Vertical medium shot. A general enters a tent; only the back of the seated ruler is visible. His face stays out of frame. " + STYLE_A + " SFX: tent flap, footsteps.", False),
("22","1-24",4,"手在画面下部，在案上画了一个圈：圈外放炮，圈内空着。上方是空白帐布。",
 "Close shot, static. A hand draws a circle on a table map: outside the circle, cannon; inside, empty. Hand low in frame, blank canvas above. " + STYLE_A + " SFX: finger on paper.", False),
("23","1-25",4,"镜头缓慢下移。敢死兵从下方摸到帐前；更大的队伍在画面深处把空营圈住。灯笼压在下缘。",
 "Vertical night shot, camera drifts slowly downward. Troops creep up on silent tents while a larger force encircles the empty camp from the deeper layer. Lanterns low in frame, black sky above. " + STYLE_A + " SFX: whispered orders, footsteps.", False),
("24","1-26",6,"全剧第一个留白爆闪。喊声大起，两支队伍在黑暗里撞在一起，都以为对方是敌人。",
 "Vertical shot with a single white flash. Shouts erupt; two forces collide in the dark believing each other to be the enemy. Chaos in the centre third, darkness above and below. " + STYLE_A + " SFX: shouts, steel, a cannon.", False),
("25","1-27",4,"一声炮响，骑兵从两侧压进来，向纵深推。人很小。",
 "Vertical wide shot. A single cannon report; riders pour in from both sides and press into depth. Men small against blank mist. " + STYLE_A + " SFX: cannon, hooves.", False),
("26","1-28",4,"跪地回话，甲上还挂着泥。人物压在画面下部，上方空白。",
 "Vertical medium shot, static. An officer kneels reporting, mud still on his armour. Figure low in frame, blank night above. " + STYLE_A + " SFX: night wind.", False),
("27","1-29",8,"镜头从他静止的脸仰起，一直摇到大片空白的夜空。他什么也没说。",
 "Vertical shot, camera tilts up from a commander's still face to a vast empty night sky. He says nothing. " + STYLE_A + " SFX: wind, no music.", False),
("28","1-30",8,"细雨。水洼压在画面下部，抱膝的军士在中部，将军立于帐口看雨，人被上方大片灰天压着。",
 "Vertical shot, static, fine steady rain. Water pools on tent roofs across the lower third; soldiers sit hugging their knees in the middle; a general stands at a tent mouth, dwarfed by blank grey sky above. " + STYLE_A + " SFX: steady rain.", False),
("29","1-31",4,"砍柴军士从坡上下来，柴堆在画面下部堆成小山。没有台词。",
 "Vertical wide shot. Woodcutters come down a slope and stack firewood; the pile grows into a small hill in the lower third. No dialogue. " + STYLE_A + " SFX: axe on wood.", False),
("30","1-32",4,"出帐观星，抬头，然后一脚一脚地顿。星在画面中上部，脚在下缘。",
 "Vertical night shot. A commander steps out, looks up at scattered stars, then stamps his foot again and again. Stars above, earth below. " + STYLE_A + " SFX: wind, a stamped boot.", False),
("31","1-33",6,"蹲在树下发抖。只给湿透的背，不给脸。",
 "Vertical close shot. Soldiers crouch under a tree, soaked through, shivering. Only wet backs and rain, no faces. " + STYLE_A + " SFX: rain, shivering breath.", False),
("32","1-34",6,"分派。抬起的手臂停在画面上部，下方是空白的地。",
 "Vertical medium shot. A general gives orders, arm raised: one son to the right slope, one to the left. The raised arm high in frame, blank ground below. " + STYLE_A + " SFX: low voices.", False),
("33","1-35",4,"士兵从画面下方涌入营寨，两侧伏兵同时升起，倒下的很多。",
 "Vertical night shot. Troops pour into a camp from below frame while two ambush parties rise from both sides — many fall. " + STYLE_A + " SFX: shouts, steel, drums.", False),
("34","1-36",6,"众臣垂手，将军来回走，一人上前。上方空白，下方是地。",
 "Vertical medium shot. Ministers stand with hands lowered; a commander paces back and forth; one official steps forward. Blank ceiling above, floor below. " + STYLE_A + " SFX: footsteps, cloth.", False),
("35","1-37",6,"镜头慢慢推近一只攥着的拳头，指头一根一根松开。上方是空，下方是案沿。",
 "Vertical close shot, camera pushes in slowly. A clenched fist relaxes, finger by finger. Blank air above, a table edge below. " + STYLE_A + " SFX: quiet.", False),
("36","1-38",4,"在回书上按印。印在画面下部，上方是空白纸。",
 "Vertical close shot, static. A ruler presses his seal onto a short letter. Seal low in frame, blank paper above. " + STYLE_A + " SFX: a soft press.", False),
("37","1-39",8,"烛光。一盏灯在中部投出一小片暖，上下一片黑。一只手从画外伸进来。",
 "Vertical shot, static, candlelit. A single lamp inside hanging drapes throws a small warm pool in the middle third; darkness above and below. One hand reaches in from off-frame. " + STYLE_A + " SFX: a candle guttering.", False),
("38","1-39",6,"烛火晃了一下。只给那只接过诏书的手，不给脸。",
 "Vertical close shot. A candle flame leans; a hand takes hold of a rolled edict. Faces stay out of frame. " + STYLE_A + " SFX: flame, paper.", False),
("39","1-40",8,"镜头缓缓升起。赭石色的旗海在画面下部展开，上方 2/3 是空白的晨光。",
 "Vertical shot, camera rises slowly. An ochre sea of banners unfurls across the lower frame under blank dawn light, sky filling the upper two thirds. " + STYLE_A + " SFX: many flags in wind.", False),
("40","1-41",6,"使者快马朝画面深处去，越跑越小。",
 "Vertical wide shot. A lone courier gallops away from camera into depth, shrinking toward a low horizon. " + STYLE_A + " SFX: hooves receding.", False),
("41","—",4,"镜头停在诏书上，不动。上下都是空。",
 "Vertical close shot, static. An open imperial edict fills the middle of frame, blank space above and below. The camera does not move. " + STYLE_A + " SFX: wind only.", False),
]

E6 = [
("01","3-36",8,"杨业请求在谷口设强弩接应；潘仁美假意应允，脸始终朝画外，座位比杨业低。上下留白。",
 "Vertical medium shot, static. A general asks a favour of a seated commander; the seated man agrees with his face turned away from camera and sits visibly lower in frame. Blank ground below, blank sky above. " + STYLE_A + " SFX: wind across a valley.", False),
("02","3-37",8,"近景。走路发僵；有人问，他说是出帐时跌了一跤。上方空白雾气。",
 "Vertical close shot. A general walks stiffly; asked why, he says he tripped leaving his tent. His face in the centre third, blank mist above. " + STYLE_A + " SFX: wind.", False),
("03","3-38",8,"儿子在劝，父亲不回头。两人都在画面下部，上方是空天。",
 "Vertical medium shot. A young officer argues with his father; the father does not turn. Both figures low in frame, empty sky above. " + STYLE_A + " SFX: wind.", False),
("04","3-39",8,"贺怀浦带部下到，行礼；杨业动容。人物在下三分之一。",
 "Vertical medium shot. An officer arrives with his men and bows; the general is visibly moved. Figures in the lower third, blank mist above. " + STYLE_A + " SFX: wind, harness.", False),
("05","3-40",8,"辽兵漫山遍野而来，分几层铺在画面下部；上方是空白天。七郎上前请战。",
 "Vertical wide shot, static. Enemy troops spread across a slope in layered depth, filling the lower frame; blank sky above. A young officer steps forward asking to go first. " + STYLE_A + " SFX: distant horns.", False),
("06","3-41",8,"偏将两合被挑下马。动作压在画面中部。",
 "Vertical medium shot. Two riders clash; one is thrown from his horse in two passes. Action in the middle third. " + STYLE_A + " SFX: steel, a shout, a fall.", False),
("07","3-42",8,"记功，然后指向峡谷深处。两侧谷壁夹住画面，上方只留一条窄天。",
 "Vertical medium shot. A general nods to record a merit and points onward down a gorge. Gorge walls press in from left and right; only a narrow band of sky above. " + STYLE_A + " SFX: wind in a narrow gorge.", False),
("08","3-43",8,"留白爆闪。破第二道谷口，敌将拨马败走。",
 "Vertical shot with one white flash. Riders break through a narrow gorge mouth; the enemy commander turns and flees. " + STYLE_A + " SFX: shouts, hooves.", False),
("09","3-44",8,"他勒住马，读两侧的谷壁，抬手止住身后队伍。谷壁从两边压进来。",
 "Vertical close shot. A general reins in, reading the gorge walls; his raised hand halts the column behind him. Walls pressing in from both sides. " + STYLE_A + " SFX: wind, held breath.", False),
("10","3-45",8,"父亲解下腰间的酒囊扔过去；儿子在马上单手接住。抛物线的顶端落在画面上三分之一。",
 "Vertical medium shot. A father unties a leather wine flask from his waist and tosses it; a young officer catches it one-handed on horseback. The toss crosses the upper third. " + STYLE_A + " SFX: a leather slap, hooves departing.", False),
("11","3-46",6,"后路被断，前路杀回，宋军被夹在谷里。人压在下部，上方是雾。",
 "Vertical wide shot, static. Troops seal the gorge mouth behind while others close in from ahead; the trapped column fills the lower frame, blank mist above. " + STYLE_A + " SFX: horns, shouts.", False),
("12","3-47",6,"高角度沿纵深俯拍：镜头顺谷道由近及远推，谷口已封死，箭从两边倾下——只见箭与石头，不见人。",
 "High angle looking down along a gorge, camera pushes slowly into depth. The mouth is sealed; arrows pour down the walls — only arrows and stone visible, no faces. The gorge runs from bottom of frame into the middle. " + STYLE_A + " SFX: arrow storm, wind.", True),
("13","3-48",6,"被一斧劈下马。动作压在画面下部，上方是空天。",
 "Vertical medium shot. An officer is struck down from horseback by a single axe blow. Action low in frame, blank sky above. " + STYLE_A + " SFX: a heavy impact.", False),
("14","3-49",6,"六郎在厮杀中回头，看见辽兵围住了父亲。两组人分处画面的前后两个深度层。",
 "Vertical medium shot. A young officer turns mid-fight and sees riders closing around an older figure. The two groups sit in separate depth planes. " + STYLE_A + " SFX: steel, shouts.", False),
("15","3-50",8,"核心镜头。父子被断为两处；他从自己的视线回望——只看得见雾和旗，什么也认不出。画面上 2/3 全是雾。",
 "Vertical wide shot, static, from the young officer's eye line. Enemy riders cut the family in two; he looks back across the gorge — mist and banners only, nothing readable. Figures low, mist filling the upper two thirds. " + STYLE_A + " SFX: wind, muffled shouts.", False),
("16","3-51",6,"身边只剩百余人。他把刀拄在地上——刀尖落在画面下三分之一，上方是空白雾。",
 "Vertical medium shot. A general stands with his sword point planted in the ground; about a hundred men remain around him. The planted blade in the lower third, blank mist above. " + STYLE_A + " SFX: wind.", False),
("17","3-52",6,"百余人齐齐跪下，面朝镜头，一层层向纵深排开。",
 "Vertical wide shot. About a hundred men kneel as one, facing camera, ranks receding into depth. Blank mist above. " + STYLE_A + " SFX: armour settling, wind.", False),
("18","3-53",6,"率众做最后一次冲杀，地上铺满倒下的人。",
 "Vertical wide shot. The general leads a last charge; the ground fills with fallen men. Action across the middle third, blank mist above. " + STYLE_A + " SFX: steel, shouts, wind.", False),
("19","3-54",8,"核心镜头。镜头从土岗上的人下摇到地面：一块歪在土里的残碑，碑侧一株枯柳，枝条全部折断。人留在上方，碑落在下三分之一。",
 "Vertical shot, camera tilts down from a group of exhausted soldiers on a hillock to a broken stele leaning in frozen earth. Beside it a dead willow, every branch snapped off. Soldiers and mist above, stele in the lower third. " + STYLE_A + " SFX: wind ceasing.", False),
("20","3-54",6,"大特写。镜头自下而上掠过碑面：一行行被磨平的刻痕往上走，最后两个停在画面正中——李陵。",
 "Vertical extreme close-up, camera tilts slowly upward across a weathered stele face. Rows of worn carving climb past frame until two characters stop at the centre: Li Ling. Stone fills all three layers, pale ochre and ink-black line. " + STYLE_A + " SFX: complete silence.", True),
("21","3-55",6,"他慢慢环视剩下的人。人物在中部，上方是雪天。",
 "Vertical medium shot, static. A wounded general looks slowly around his remaining men. His figure in the centre, blank snow sky above. " + STYLE_A + " SFX: wind.", False),
("22","3-55",6,"整理甲胄：系好最后一颗甲片，拢须，叠好披风放在碑脚，把刀插进土里。很慢，很稳，全是日常动作。",
 "Vertical medium shot, static. A general fastens the last plate of his armour, smooths his beard, folds his torn cloak and lays it at the foot of the stele, then plants his sword in the earth. Slow, steady, ordinary. " + STYLE_A + " SFX: wind only, no music.", False),
("23","3-56",6,"全片风格高潮。镜头从他背后升起，越过肩，对着那块碑。他向前三步，一头撞去——最后一帧抽掉全部颜色，只剩黑白与刀穗上一点朱砂。",
 "Vertical shot, camera rises slowly from behind a lone armoured figure, passing over his shoulder toward a blank stele. He takes three steps and lunges. On the final frame all colour drains to black, white and grey, with a single cinnabar-red note on the sword tassel. Flat shapes of ink. " + STYLE_A + " SFX: wind, then one low dull impact.", False),
("24","3-57",6,"数十人以一当十，尽都战死——但镜头不跟人，只停在空地上，看雪落进下三分之一。",
 "Vertical wide shot, static. The last handful fight and fall, but the camera does not follow them: it holds on empty ground while snow falls into the lower third. Blank sky above. " + STYLE_A + " SFX: wind, one distant cry.", False),
("25","3-57",6,"黑场。什么都看不见，只有风声，和一句旁人听不见的话。",
 "Vertical shot fading fully to black. Nothing visible; only wind. " + STYLE_A + " SFX: long wind, one whispered line.", False),
("26","3-58",6,"他关上帐门，插闩，一个人坐下喝酒。灯压在画面下部，上方一片黑。",
 "Vertical night shot. A man closes a tent flap and bars it, then sits alone drinking. Lamp low in frame, black night above. " + STYLE_A + " SFX: lamp, drink being poured.", False),
("27","3-59",6,"七郎被军士拦住，拔剑，推开帐门闯进去。动作压在画面中部。",
 "Vertical night shot. A young officer is stopped by guards, draws his blade and pushes through the tent flap. Action in the centre third, black night above and below. " + STYLE_A + " SFX: steel drawn, fabric torn.", False),
("28","3-60",6,"从他背后拍：只到肩，不给脸。他强按怒火诉说求援；帐内那人远远地在画面深处，很小。",
 "Vertical medium shot from behind. A young officer argues and pleads; the camera holds at his shoulders — his face never shown. The seated man is small in the deeper layer. " + STYLE_A + " SFX: low voices.", False),
("29","3-61",6,"坐着的人抬起两根手指；军士上前把他捆起来。他的身影压在画面下部。",
 "Vertical medium shot. The seated man lifts two fingers; guards move in and bind the young officer. The bound figure low in frame. " + STYLE_A + " SFX: rope, struggle.", False),
("30","3-62",6,"他大骂不止。镜头自下而上竖移，扫过两旁军士的脸——一个接一个都在下泪。脸在画面中轴上一层层升起。",
 "Vertical shot, camera tilts slowly upward across the faces of the guards on either side — each one weeping as they hold him. Faces stacked up the centre of frame, black night above. " + STYLE_A + " SFX: shouting, then quiet.", True),
("31","3-63",6,"镜头抬起来，只看天。一片云从月亮前面走过去，光的边缘变了一次。别的什么都不给。",
 "Vertical shot, camera tilts up to the sky only. One cloud crosses the moon; the edge of the light changes once. Nothing else framed. " + STYLE_A + " SFX: a volley of bowstrings, then wind, then one soft drumbeat.", False),
]

HOLD_CHECKS = [
 ("① 竖屏三层结构立不立得住", "看每镜的「上天下地中间人」是否成立，特别是空镜与远景。判据：不靠字幕，只看画面就知道人在哪、事在哪。"),
 ("② 那 8 个改写镜头的运镜对不对", "第 1 集的 01/02/08/11/14 和第 6 集的 12/20/30。判据：竖屏里信息没有丢，观众不觉得「少了半边」。"),
 ("③ 慢节奏能不能撑住竖屏", "本片平均 6.2 秒/镜，比短视频常规的 2–3 秒慢一倍。判据：连续看 3 分 30 秒会不会闷。这一条决定整个风格能不能走。"),
 ("④ 朱砂那一点还灵不灵", "第 6 集镜 23 是全片风格高潮（抽掉全部颜色只留一点朱砂）。判据：在竖屏小尺寸下，那一点红还看得出来吗？"),
 ("⑤ 不给脸的处理行不行", "第 1 集镜 17/18/21/38、第 6 集镜 28/30 都是「不给脸」。判据：观众能不能从背影和手读出情绪。"),
 ("⑥ 李陵碑三镜的同机位基础", "第 6 集镜 19/20/23 是碑的第一次出现，第 8 集与第 24 集要复用同一机位。判据：这三镜的碑位、柳位、刀位能不能被锁定成一套场景资产。"),
 ("⑦ 开场的钩子留不留人", "第 1 集镜 01 是「空镜平摇→竖摇」的开场。判据：前 3 秒跳出率。若不行，动钩子不动结构。"),
 ("⑧ 生产成本是否可控", "72 镜 Lite 档 = 720 积分。判据：一次跑通率有多高？返工率超过 40% 说明提示词写法要改。"),
]

CSS = """
:root{--paper:#FBF8F1;--card:#FFF;--ink:#231F19;--ink2:#4A443B;--ink3:#7A7266;--line:#E3DCCC;--line2:#D2C8B2;
--zhu:#B03A2E;--zhu-bg:#F6E7E4;--green:#3E6B5A;--green-bg:#E6EFE9;--jin:#B8912B;--jin-bg:#F8F1DC;--dai:#3E4E5A;--dai-bg:#E8EDF0;}
*{box-sizing:border-box;}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"PingFang SC","Microsoft YaHei","Hiragino Sans GB",sans-serif;font-size:15px;line-height:1.82;}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px 90px;}
h1{font-family:"Songti SC","SimSun",serif;font-size:32px;margin:44px 0 6px;letter-spacing:.03em;}
h1 small{display:block;font-size:14.5px;color:var(--ink2);font-weight:400;margin-top:10px;letter-spacing:.06em;}
h2{font-family:"Songti SC","SimSun",serif;font-size:21px;margin:44px 0 14px;padding-bottom:11px;border-bottom:2px solid var(--ink);}
h3{font-size:16.5px;margin:26px 0 10px;padding-left:11px;border-left:4px solid var(--zhu);}
.lead{color:var(--ink2);border-left:3px solid var(--line2);padding-left:14px;margin:0 0 22px;}
.tw{overflow-x:auto;margin:0 0 20px;}
table{width:100%;border-collapse:collapse;background:var(--card);font-size:13px;line-height:1.7;border:1px solid var(--line2);}
th,td{padding:9px 11px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top;}
thead th{background:var(--ink);color:#F7F3EA;font-size:12.5px;font-weight:600;border-bottom:none;}
tbody tr:nth-child(even){background:#FCFAF5;}
td.c{text-align:center;white-space:nowrap;font-variant-numeric:tabular-nums;}
.note{background:var(--zhu-bg);border:1px solid #E9C9C4;border-radius:8px;padding:15px 19px;margin:0 0 18px;font-size:14px;}
.note b{color:var(--zhu);}
.green{background:var(--green-bg);border:1px solid #C2D6CB;border-radius:8px;padding:15px 19px;margin:0 0 18px;font-size:14px;}
.green b{color:var(--green);}
.gold{background:var(--jin-bg);border:1px solid #E4D3A0;border-radius:8px;padding:15px 19px;margin:0 0 18px;font-size:14px;}
.dai{background:var(--dai-bg);border:1px solid #C9D6DE;border-radius:8px;padding:15px 19px;margin:0 0 18px;font-size:14px;}
.dai b{color:var(--dai);}
code{font-family:ui-monospace,Consolas,monospace;font-size:12px;background:#F1ECE0;padding:1px 5px;border-radius:3px;}
.kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:0 0 22px;}
@media(max-width:760px){.kpi{grid-template-columns:repeat(2,1fr);}}
.kpi div{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:15px 17px;border-top:3px solid var(--zhu);}
.kpi .v{font-family:"Songti SC",serif;font-size:27px;font-weight:700;line-height:1.15;}
.kpi .l{font-size:12.5px;color:var(--ink3);margin-top:3px;}
.shot{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:0;margin-bottom:14px;overflow:hidden;}
.shot.rw{border-left:4px solid var(--zhu);}
.shot .hd{display:flex;align-items:center;gap:11px;padding:10px 16px;background:#F4F0E6;border-bottom:1px solid var(--line);flex-wrap:wrap;}
.shot.rw .hd{background:var(--zhu-bg);}
.shot .hd .no{font-family:"Songti SC",serif;font-size:20px;font-weight:700;color:var(--zhu);line-height:1;}
.shot .hd .mk{font-size:11.5px;color:var(--ink3);font-family:ui-monospace,Consolas,monospace;}
.shot .hd .tg{font-size:11.5px;background:#fff;border:1px solid var(--line2);border-radius:20px;padding:1px 9px;color:var(--ink2);}
.shot .hd .tg.rw{background:var(--zhu);color:#fff;border-color:var(--zhu);font-weight:600;}
.shot .bd{padding:13px 16px;}
.shot .cn{font-size:13.5px;color:var(--ink2);background:#FAF7F0;border-left:3px solid var(--line2);padding:10px 13px;margin:0 0 11px;}
.prow{position:relative;background:#F4F0E6;border:1px solid var(--line2);border-radius:7px;padding:12px 14px;}
.prow pre{margin:0;font-family:ui-monospace,Consolas,monospace;font-size:12.5px;line-height:1.75;white-space:pre-wrap;color:#2B2620;}
.cp{position:absolute;top:8px;right:8px;background:#1A73E8;color:#fff;border:none;border-radius:5px;padding:4px 10px;font-size:11.5px;cursor:pointer;font-family:inherit;}
.cp:hover{background:#1557B0;}
.steps{counter-reset:s;list-style:none;padding:0;margin:0 0 20px;}
.steps li{counter-increment:s;position:relative;padding:0 0 14px 42px;font-size:14.5px;}
.steps li::before{content:counter(s);position:absolute;left:0;top:2px;width:26px;height:26px;border-radius:50%;background:var(--ink);color:#F7F3EA;font-size:12.5px;font-weight:700;display:flex;align-items:center;justify-content:center;}
.badge{display:inline-block;font-size:11.5px;padding:2px 9px;border-radius:20px;font-weight:600;margin-right:6px;}
.b-z{background:var(--zhu-bg);color:var(--zhu);}
.b-g{background:var(--green-bg);color:var(--green);}
"""


def main():
    P = []
    rw1 = sum(1 for r in E1 if r[5]); rw6 = sum(1 for r in E6 if r[5])
    t1 = sum(r[2] for r in E1); t6 = sum(r[2] for r in E6)
    P.append("""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>杨家将 · 忠烈千秋 —— 试播集制作包</title><style>@@CSS@@</style></head><body><div class="wrap">
<h1>杨家将 · 忠烈千秋 · 试播集制作包
<small>第 1 集《北汉风雪》41 镜 ＋ 第 6 集《李陵碑 · 殉国》31 镜 ＝ 72 镜 · 9:16 · Lite 档 · 约 720 积分</small></h1>
<p class="lead">按三步走的第一步排的。这 72 镜<b>不是拿去出片的，是拿去验证竖屏改法的</b>——特别是那 8 个横屏运镜在竖屏里会失效的镜头。每镜都已改写成竖屏构图，并配好可直接粘贴的 Flow 英文提示词。</p>

<div class="dai"><b>用法</b>　每镜先用 Frames to Video 把首帧放上去，再粘贴英文提示词。<b>因为首帧已经锁死了构图与画风，提示词只写运镜、最小动作与音效</b>——所以都很短（30–70 词），Lite 档也能吃得住。</div>

<div class="kpi">
  <div><div class="v">72</div><div class="l">镜头总数（41 + 31）</div></div>
  <div><div class="v">%d</div><div class="l">需重写运镜的镜头</div></div>
  <div><div class="v">7:00</div><div class="l">成片时长（两支 3:30）</div></div>
  <div><div class="v">720</div><div class="l">Lite 档积分</div></div>
</div>

<h2>一、这 72 镜要回答的 8 个问题</h2>
<p class="lead">试播集的价值不在"好看"，在"能不能拿到判断"。下面每一条都给了判据，看完片子逐条打勾或打叉。</p>
<div class="tw"><table>
<thead><tr><th style="width:230px;">要验证的</th><th>判据</th></tr></thead><tbody>""" % (rw1 + rw6))
    for a, b in HOLD_CHECKS:
        P.append("<tr><td><b>%s</b></td><td>%s</td></tr>" % (a, b))
    P.append("""</tbody></table></div>
<div class="note"><b>如果第 ③ 条（慢节奏撑不住）挂了，整个 B 方案要重估。</b>其余七条都是可修的——构图能调、钩子能换、成本能压。只有节奏是风格的命根子，改不了。所以看片时优先盯这一条。</div>

<h2>二、8 个重写镜头的对照</h2>
<p class="lead">这 8 个是横屏专属运镜在竖屏里会失效的镜头。左边是原版，右边是竖屏改法。<b>其余 64 镜是"直接可用"或只需微调，但整集我都按竖屏三层结构重排了一遍</b>。</p>
<div class="tw"><table>
<thead><tr><th class="c" style="width:52px;">集</th><th class="c" style="width:50px;">镜</th><th style="width:120px;">横屏原运镜</th><th style="width:140px;">竖屏改法</th><th>为什么</th></tr></thead><tbody>
<tr><td class="c">1</td><td class="c">01</td><td>远景平摇</td><td><b>竖摇（自下而上）</b></td><td>横摇扫景在竖屏里两侧全在画外。改成先入影子、再入人、最后停在天与雪线</td></tr>
<tr><td class="c">1</td><td class="c">02</td><td>中景横移</td><td><b>沿纵深退开</b></td><td>九个人横着排不进竖屏。改成从前景到后景一层层退出来，颜色依旧一层一色</td></tr>
<tr><td class="c">1</td><td class="c">08</td><td>远景横移</td><td><b>自下方走入、向深处去</b></td><td>「从左走到右」改成「从下走向深处」，信息不减，方向从横变纵</td></tr>
<tr><td class="c">1</td><td class="c">11</td><td>俯拍（横向）</td><td><b>高角度沿纵深俯拍</b></td><td>保留俯视，但镜头顺着地图由近及远推，不横着扫</td></tr>
<tr><td class="c">1</td><td class="c">14</td><td>远景平摇</td><td><b>竖摇：蹄→人→旗</b></td><td>两军对撞的横向展开改竖向递进，冲击感反而更强</td></tr>
<tr><td class="c">6</td><td class="c">12</td><td>俯拍（横向）</td><td><b>高角度沿纵深俯拍</b></td><td>箭雨沿谷道纵深倾下，比横向扫更压抑</td></tr>
<tr><td class="c">6</td><td class="c">20</td><td>大特写横移</td><td><b>竖移（自下而上）</b></td><td>碑面刻痕往上走，最后两个字停在画面正中——竖屏里"停在正中"比"移到右边"更狠</td></tr>
<tr><td class="c">6</td><td class="c">30</td><td>近景横移</td><td><b>竖移：扫过两旁的脸</b></td><td>军士的脸在画面中轴上一层层升起，比横着一排更压迫</td></tr>
</tbody></table></div>

<h2>三、第 1 集《北汉风雪》· 41 镜</h2>
<p class="lead">总 %d 秒 · 需改写运镜 %d 镜。<span class="badge b-z">红框</span>为需改写运镜的镜头。</p>""" % (t1, rw1))
    for r in E1:
        idx, mk, dur, cn, en, rw = r
        P.append("""<div class="shot%s">
<div class="hd"><div class="no">%s</div><span class="mk">原书 %s</span><span class="tg">%d 秒</span>%s</div>
<div class="bd"><p class="cn"><b>竖屏画面</b>　%s</p>
<div class="prow"><button class="cp" onclick="cp(this)">复制</button><pre>%s</pre></div></div></div>"""
                 % (" rw" if rw else "", idx, mk, dur,
                    '<span class="tg rw">需改写运镜</span>' if rw else "", cn, en))

    P.append("""<h2>四、第 6 集《李陵碑 · 殉国》· 31 镜</h2>
<p class="lead">总 %d 秒 · 需改写运镜 %d 镜。这一集是全片第一个高潮，也是李陵碑意象的出生地——<b>镜 19、20、23 的碑位、柳位、刀位必须被锁进场景资产 S10</b>，第 8 集与第 24 集要复用同一机位。</p>""" % (t6, rw6))
    for r in E6:
        idx, mk, dur, cn, en, rw = r
        P.append("""<div class="shot%s">
<div class="hd"><div class="no">%s</div><span class="mk">原书 %s</span><span class="tg">%d 秒</span>%s</div>
<div class="bd"><p class="cn"><b>竖屏画面</b>　%s</p>
<div class="prow"><button class="cp" onclick="cp(this)">复制</button><pre>%s</pre></div></div></div>"""
                 % (" rw" if rw else "", idx, mk, dur,
                    '<span class="tg rw">需改写运镜</span>' if rw else "", cn, en))

    P.append("""<h2>五、执行顺序</h2>
<ol class="steps">
<li><b>先出首帧（72 张）</b>用锁定的色盘与角色锚点批量出图。风格锚定用已有的六镜样张。<b>第 6 集镜 19/20/23 要优先出</b>——它们是李陵碑场景的基准，第 8 集和第 24 集要靠它对齐。</li>
<li><b>只跑那 8 个改写镜头</b>先拿第 1 集的 01/02/08/11/14 和第 6 集的 12/20/30 试。8 段 × Lite 10 积分 = <b>80 积分</b>。这 8 个成立，竖屏改法就成立；不成立，后面 64 镜不用跑。</li>
<li><b>再跑整集</b>72 段 × Lite 10 积分 = <b>720 积分</b>。按集推进，先把第 1 集跑完看节奏，再跑第 6 集。</li>
<li><b>剪成两支 3 分 30 秒</b>按切分表的顺序硬切拼接。旁白单独合成后铺上（不交给 Flow）。</li>
<li><b>按第一章的 8 条判据过一遍</b>重点看第 ③ 条（慢节奏能不能撑住竖屏）。</li>
</ol>
<div class="green"><b>省积分的两条</b>　① 先跑 8 镜验证（80 积分），不要直接跑 72 镜；② 一次跑通率如果低于 60%，先回头改提示词写法，别急着补跑——补跑是十倍成本。</div>

<h2>六、首帧清单要点</h2>
<div class="tw"><table>
<thead><tr><th style="width:180px;">资产</th><th>本试播集需要</th><th class="c" style="width:70px;">张数</th></tr></thead><tbody>
<tr><td><b>C01 杨业</b></td><td>第 1 集 9 镜、第 6 集 12 镜。需要四视图 + 三套状态（常服 / 亮甲 / 残甲）</td><td class="c">约 15</td></tr>
<tr><td><b>C03 杨延平 / C04 杨延昭 / C05 杨延嗣</b></td><td>第 1 集列队与交战、第 6 集七郎的戏。三人各四视图</td><td class="c">约 12</td></tr>
<tr><td><b>C02 佘太君</b></td><td>第 1 集营门目送、第 2 集接印</td><td class="c">约 4</td></tr>
<tr><td><b>C11 潘仁美 / C12 王侁</b></td><td>第 1 集被打落马、第 6 集帐内假意应允</td><td class="c">约 6</td></tr>
<tr><td><b>C13 宋太宗</b></td><td>第 1 集帐内、观星、抬头看天</td><td class="c">约 5</td></tr>
<tr><td><b>S10 李陵碑</b></td><td><b>最重要。</b>第 6 集镜 19/20/23 是基准机位，要一次出准</td><td class="c">3 机位</td></tr>
<tr><td><b>S01 代州城头 / S04 校场 / S06 邠阳城 / S08 陈家谷</b></td><td>两集的主要场景，各正打反打侧面三机位</td><td class="c">约 12</td></tr>
<tr><td><b>其余</b></td><td>按镜逐个补</td><td class="c">余数</td></tr>
</tbody></table></div>
<div class="gold"><b>出图顺序建议</b>　先出 <b>C01 杨业</b>（三套状态）和 <b>S10 李陵碑</b>（三机位）——这两个定下来，第 6 集就能整集出图了。第 1 集涉及的人多，放到第二批。</div>

<p style="font-size:13px;color:#7A7266;margin-top:28px;">
本制作包中的故事取自传统民间杨家将传说与《宋史》等公共素材。原连环画《北宋杨家将》（湖南美术出版社，喻岳衡改编，蒋太禄等绘）的画面与改编文字著作权归原作者与出版方所有，本方案不含任何原画复用。<br>
Flow / Veo 3.1 规格（4/6/8 秒档位、Lite 10 / Fast 20 / Quality 100 积分）核对于 2026 年 9 月，平台规则可能变动，投产前建议在界面内再确认。</p>
</div>
<script>
function cp(b){const t=b.parentNode.querySelector('pre').innerText;
 navigator.clipboard.writeText(t).then(()=>{b.textContent='已复制';setTimeout(()=>b.textContent='复制',1400);},
 ()=>{const r=document.createRange();r.selectNodeContents(b.parentNode.querySelector('pre'));
 const s=getSelection();s.removeAllRanges();s.addRange(r);});}
</script>
</body></html>""")

    html = "".join(P).replace("@@CSS@@", CSS)
    open(OUTH, "w", encoding="utf-8").write(html)

    # ---------- XLSX ----------
    C_ = "231F19"; ZHU = "B03A2E"; ALT = "FCFAF5"
    thin = Side(style="thin", color="D2C8B2")
    BD = Border(left=thin, right=thin, top=thin, bottom=thin)
    wb = Workbook()

    def mk(ws, headers, body, widths, ctr=()):
        ws.append(headers)
        for c in range(1, len(headers) + 1):
            cell = ws.cell(1, c)
            cell.font = Font(bold=True, color="F7F3EA", size=10.5, name="Microsoft YaHei")
            cell.fill = PatternFill("solid", fgColor=C_)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = BD
        ws.row_dimensions[1].height = 28
        for i, r in enumerate(body, start=2):
            ws.append(list(r))
            for c in range(1, len(headers) + 1):
                cell = ws.cell(i, c)
                cell.font = Font(size=9.5, name="Microsoft YaHei")
                cell.alignment = Alignment(vertical="top", wrap_text=True,
                                           horizontal="center" if c in ctr else "left")
                cell.border = BD
                if i % 2 == 0:
                    cell.fill = PatternFill("solid", fgColor=ALT)
        for k, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(k)].width = w
        ws.freeze_panes = "A2"

    ws1 = wb.active
    ws1.title = "试播集72镜"
    body = []
    for ep, data in ((1, E1), (6, E6)):
        for idx, mk_, dur, cn, en, rw in data:
            body.append([ep, idx, mk_, dur, ("是" if rw else "—"), cn, en])
    mk(ws1, ["集", "镜序", "原书页", "段长(秒)", "需改运镜", "竖屏画面（中文）", "Flow 英文提示词"],
       body, [5, 7, 9, 9, 9, 60, 82], ctr=(1, 2, 3, 4, 5))

    ws2 = wb.create_sheet("验证清单8条")
    mk(ws2, ["#", "要验证的", "判据", "结论"], [[i, a, b, ""] for i, (a, b) in enumerate(HOLD_CHECKS, 1)],
       [5, 40, 78, 14], ctr=(1,))

    ws3 = wb.create_sheet("执行顺序与积分")
    mk(ws3, ["步骤", "内容", "段数", "档位", "积分", "说明"], [
        ["1", "首帧出图（72 张）", 72, "出图", "360–720", "按 C01 杨业 + S10 李陵碑 优先"],
        ["2", "先跑 8 个改写镜头", 8, "Lite", 80, "验证竖屏改法是否成立。不成立则后面 64 镜不跑"],
        ["3", "跑第 1 集剩余", 33, "Lite", 330, "41 镜 − 已跑 8 镜（其中 5 镜在第 1 集）"],
        ["4", "跑第 6 集全部", 31, "Lite", 310, "含 3 个改写镜头"],
        ["5", "合计（Lite 全量）", 72, "Lite", 720, "第一步预算"],
        ["6", "通过后升 Fast（约 30 镜）", 30, "Fast", 600, "第二步：出两支 3:30 样片"],
        ["7", "定稿升 Quality（仅关键段）", "≤10", "Quality", "≤1000", "李陵碑三镜 + 殉国 + 挂帅"],
    ], [6, 30, 8, 10, 10, 50], ctr=(1, 3, 4, 5))

    wb.save(OUTX)
    return len(body), rw1 + rw6


try:
    n, rw = main()
    msg = "OK 镜数=%d 改写=%d\nHTML -> %s\nXLSX -> %s" % (n, rw, OUTH, OUTX)
except Exception:
    msg = "FATAL\n" + traceback.format_exc()
open(LOG, "w", encoding="utf-8").write(msg)
print("done")
