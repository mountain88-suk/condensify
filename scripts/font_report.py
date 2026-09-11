#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font_report.py —— 字体体检：拿到一个字体先看清楚它是什么、缺什么、能不能改

用法:
    python3 font_report.py 字体文件 [选项]

选项:
    --text "要检测的文字"    检查这些字在不在字体里
    --json                   输出 JSON（供脚本消费）
    --sample                 随机抽取各区字符做覆盖率展示

输出: 轮廓格式 / 字形数 / 各区覆盖 / 缺字 / 字面度量 / 许可声明 / 改造建议
"""

import argparse
import json
import random
import sys
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen

# 字符分区：(名称, 起始, 结束, 该区总容量)
ZONES = [
    ("拉丁基本", 0x0020, 0x007F, 95),
    ("拉丁补充", 0x00A0, 0x00FF, 95),
    ("通用标点", 0x2000, 0x206F, 111),
    ("CJK标点", 0x3000, 0x303F, 64),
    ("日文假名", 0x3040, 0x30FF, 192),
    ("韩文音节", 0xAC00, 0xD7A3, 11172),
    ("CJK基本区", 0x4E00, 0x9FFF, 20992),
    ("CJK扩展A", 0x3400, 0x4DBF, 6592),
    ("CJK兼容", 0xF900, 0xFAFF, 512),
    ("全角符号", 0xFF01, 0xFF60, 96),
]

# 简体常用字（用于快速判断"这字体能不能打简体"）
SIMPLIFIED_PROBE = "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社义事平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别她手角期根论运农指几九区强放决西被干做必战先回则任取据处队南给色光门即保治北造百规热领七海口东导器压志世金增争济阶油思术极交受联什认六共权收证改清己美再采转更单风切打白教速花带安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科张信马节话米整空元况今集温传土许步群广石记需段研界拉林律叫且究观越织装影算低持音众书布复容儿须际商非验连断深难近矿千周委素技备半办青省列习响约支般史感劳便团往酸历市克何除消构府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格养易置派层片始却专状育厂京识适属圆包火住调满县局照参红细引听该铁价严首底液官德随病苏失尔死讲配女黄推显谈罪神艺呢席含企望密批营项防举球英氧势告李台落木帮轮破亚师围注远字材排供河态封另施减树溶怎止案言士均武固叶鱼波视仅费紧爱左章早朝害续轻服试食充兵源判护司足某练差致板田降黑犯负击范继兴似余坚曲输修的故城夫够送笔船占右财吃富春职觉汉画功巴跟虽杂飞检吸助升阳互初创抗考投坏策古径换未跑留钢曾端责站简述钱副尽帝射草冲承独令限阿宣环双请超微让控州良轴找否纪益依优顶础载倒房突坐粉敌略客袁冷胜绝析块剂测丝协重诉念陈仍罗盐友洋错苦夜刑移频逐靠混母短皮终聚汽村云哪既距卫停烈央察烧行迅境若印洲刻括激孔搞甚室待核校散侵吧甲游久菜味旧模湖货损预阻毫普稳乙妈植息扩银语挥酒守拿序纸医缺雨吗针刘啊急唱误训愿审附获茶鲜粮斤孩脱硫肥善龙演父渐血欢械掌歌沙著刚攻谓盾讨晚粒乱燃矛乎杀药宁鲁贵钟煤读班伯香介迫句丰培握兰担弦蛋沉假穿执答乐谁顺烟缩征脸喜松脚困异免背星福买染井概慢怕磁倍祖皇促静补评翻肉践尼衣宽扬棉希伤操垂秋宜氢套笔督振架亮末宪庆编牛触映雷销诗座居抓裂胞呼娘景威绿晶厚盟衡鸡孙延危胶还屋乡临陆顾掉呀灯岁措束耐剧玉赵跳哥季课凯胡额款绍卷齐伟蒸殖永宗苗川炉岩弱零杨奏沿露杆探滑镇饭浓航怀赶库夺伊灵税途灭赛归召鼓播盘裁险康唯录菌纯借糖盖横符私努堂域枪润幅哈竟熟虫泽脑壤碳欧遍侧寨敢彻虑斜薄庭纳弹饲伸折麦湿暗荷瓦塞床筑恶户访塔奇透梁刀旋迹卡氯遇份毒泥退洗摆灰彩卖耗夏择忙铜献硬予繁圈雪函亦抽篇阵阴丁尺追堆雄迎泛爸楼避谋吨野猪旗累偏典馆索秦脂潮爷豆忽托惊塑遗愈朱替纤粗倾尚痛楚谢奋购磨君池旁碎骨监捕弟暴割贯殊释词亡壁顿宝午尘闻揭炮残冬桥妇警综招吴付浮遭徐您摇谷赞箱隔订男吹园纷唐败宋玻巨耕坦荣闭湾键凡驻锅救恩剥凝碱齿截炼麻纺禁废盛版缓净睛昌婚涉筒嘴插岸朗庄街藏姑贸腐奴啦惯乘伙恢匀纱扎辩耳彪臣亿璃抵脉秀萨俄网舞店喷纵寸汗挂洪贺闪柬爆烯津稻墙软勇像滚厘蒙芳肯坡柱荡腿仪旅尾轧冰贡登黎削钻勒荒疫死叙夹符";
# 上面含常见简体；下面再补一级字库高频
SIMPLIFIED_PROBE += "们个这来时说国语车马门问间题汉简体关动实现种产长书华东风龙会过还对开发经啊"


def zone_stats(cps):
    out = []
    for name, lo, hi, total in ZONES:
        n = sum(1 for c in cps if lo <= c <= hi)
        out.append((name, lo, hi, n, total))
    return out


def measure_latin_and_cjk(font, cmap):
    """量出汉字字面：高 / 宽 / 中心，用于后续补字对齐。"""
    gs = font.getGlyphSet()
    probe = [c for c in "山水天力大日月口木火土人心手目白田甲由申" if ord(c) in cmap]
    if not probe:
        return None
    hs, ws, cxs, cys = [], [], [], []
    for ch in probe:
        gn = cmap[ord(ch)]
        bp = BoundsPen(gs)
        gs[gn].draw(bp)
        if not bp.bounds:
            continue
        x0, y0, x1, y1 = bp.bounds
        ws.append(x1 - x0); hs.append(y1 - y0)
        cxs.append((x0 + x1) / 2); cys.append((y0 + y1) / 2)
    if not hs:
        return None
    avg = lambda a: round(sum(a) / len(a))
    return {"sample": "".join(probe), "height": avg(hs), "width": avg(ws),
            "center_x": round(sum(cxs) / len(cxs)), "center_y": round(sum(cys) / len(cys))}


def license_scan(font):
    texts = []
    for rec in font["name"].names:
        if rec.nameID in (0, 13, 14):
            try:
                texts.append(rec.toUnicode())
            except Exception:
                pass
    blob = " ".join(texts)
    low = blob.lower()
    rfn = "reserved font name" in low
    if "open font license" in low or "sil ofl" in low or "ofl 1.1" in low:
        verdict = "OFL（允许修改与再分发）" + ("，但含保留字体名，衍生版必须改名" if rfn else "")
        safe = True
    elif "apache" in low:
        verdict = "Apache（允许修改与再分发）"
        safe = True
    elif "public domain" in low or "gpl" in low and "font exception" in low:
        verdict = "公共领域 / GPL+FE（允许修改）"
        safe = True
    elif any(k in blob for k in ("수정", "修改", "as-is", "원본", "그대로")):
        verdict = "⚠ 检出「禁止修改 / 须原样使用」字样，改前务必确认条款"
        safe = False
    else:
        verdict = "? 未检出明确许可，需人工确认"
        safe = None
    return {"verdict": verdict, "safe": safe, "rfn": rfn, "raw": texts[:3]}


def report(path, text=None, sample=False, as_json=False):
    font = TTFont(path, fontNumber=0)
    cmap = font.getBestCmap()
    cps = set(cmap)
    tables = set(font.keys())
    outline = "OpenType/CFF (OTF)" if "CFF " in tables else \
              ("TrueType (glyf)" if "glyf" in tables else "未知")

    data = {
        "file": path,
        "family": None,
        "outline": outline,
        "units_per_em": font["head"].unitsPerEm,
        "glyphs": font["maxp"].numGlyphs,
        "codepoints": len(cps),
        "zones": [{"name": n, "range": f"U+{lo:04X}-{hi:04X}",
                   "count": c, "total": t} for n, lo, hi, c, t in zone_stats(cps)],
        "has_hinting": any(t in tables for t in ("fpgm", "prep", "cvt ")),
        "metrics": measure_latin_and_cjk(font, cmap),
        "license": license_scan(font),
    }
    for rec in font["name"].names:
        if rec.nameID == 1:
            try:
                data["family"] = rec.toUnicode()
                break
            except Exception:
                pass

    # 汉字 advance width（取全角代表字）
    for probe in ("山", "水", "一", "Ａ"):
        if ord(probe) in cmap:
            data["cjk_advance"] = font["hmtx"][cmap[ord(probe)]][0]
            break

    # 简体可用度
    simp = [c for c in dict.fromkeys(SIMPLIFIED_PROBE) if 0x4E00 <= ord(c) <= 0x9FFF]
    have = sum(1 for c in simp if ord(c) in cps)
    data["simplified"] = {"probed": len(simp), "covered": have,
                          "ratio": round(100 * have / len(simp), 1) if simp else 0,
                          "missing": "".join([c for c in simp if ord(c) not in cps][:60])}

    # 脚本覆盖检测：用于网页自动选择预览文字（英文 / 韩文 / 中文）
    def _covered(text):
        return all(ord(c) in cps for c in text if c.strip())
    data["script_coverage"] = {
        "latin": _covered("ABCD efgh"),
        "hangul": _covered("좋은사랑 나누자"),
        "cjk": _covered("祝你天天开心哇"),
    }

    if text:
        miss = [c for c in dict.fromkeys(text) if c.strip() and ord(c) not in cps]
        data["text_check"] = {"text": text, "missing": miss,
                              "ok": not miss}

    if sample:
        picks = {}
        for name, lo, hi, c, t in zone_stats(cps):
            avail = [x for x in cps if lo <= x <= hi]
            picks[name] = "".join(chr(x) for x in random.sample(avail, min(18, len(avail)))) if avail else ""
        data["samples"] = picks

    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return data

    # ---------- 人类可读输出 ----------
    print("=" * 68)
    print(f"字体体检报告")
    print("=" * 68)
    print(f"文件      : {data['file']}")
    print(f"字体名    : {data['family']}")
    print(f"轮廓格式  : {data['outline']}")
    print(f"em 单位   : {data['units_per_em']}    字形数: {data['glyphs']}    码位数: {data['codepoints']}")
    print(f"Hinting   : {'有（改造后需清除）' if data['has_hinting'] else '无'}")
    if data.get("cjk_advance"):
        print(f"汉字字宽  : {data['cjk_advance']}")
    print()
    print("── 字符覆盖 ──")
    for z in data["zones"]:
        if z["count"] == 0:
            continue
        bar = "█" * min(30, max(1, round(30 * z["count"] / z["total"])))
        print(f"  {z['name']:<10} {z['range']:<16} {z['count']:>6}/{z['total']:<6} {bar}")
    print()
    s = data["simplified"]
    print(f"── 简体中文可用度 ──")
    print(f"  探测 {s['probed']} 个常用简体字 → 覆盖 {s['covered']} 个 ({s['ratio']}%)")
    if s["missing"]:
        print(f"  缺失示例: {s['missing']}")
    else:
        print(f"  ✓ 简体全覆盖")
    print()
    if text:
        t = data["text_check"]
        if t["ok"]:
            print(f"── 指定文字 ──\n  ✓ 「{text}」全部有字形")
        else:
            print(f"── 指定文字 ──\n  ⚠ 「{text}」缺 {len(t['missing'])} 个: {' '.join(t['missing'])}")
        print()
    if data["metrics"]:
        m = data["metrics"]
        print(f"── 汉字字面度量（用于补字对齐）──")
        print(f"  样字 {m['sample']}")
        print(f"  平均 高 {m['height']} / 宽 {m['width']} / 中心 ({m['center_x']}, {m['center_y']})")
        print()
    lic = data["license"]
    print(f"── 许可 ──")
    print(f"  {lic['verdict']}")
    if lic.get("rfn"):
        print("  ⚠ 含保留字体名(Reserved Font Name)：衍生版不能用原字体名，必须另起名（本工具已自动改名）")
    for r in lic["raw"][:2]:
        if r.strip():
            print(f"  · {r[:150]}")
    print()
    print("── 改造建议 ──")
    if data["outline"].startswith("TrueType"):
        print("  · 收窄：直接跑 condense_font.py，无轮廓转换损耗")
    else:
        print("  · 收窄：condense_font.py 可直接处理；若要合并到 TTF 目标，补字需 CFF→TTF 转换")
    if s["ratio"] < 95 and s["ratio"] >= 0:
        print(f"  · 简体缺 {100 - s['ratio']:.0f}%，建议用 Noto Sans SC（OFL）补齐：fill_missing.py")
    if not lic["safe"]:
        print("  · ⚠ 许可不允许修改，改后请仅自用，勿外发/商用交付")
    print("=" * 68)
    return data


def main():
    ap = argparse.ArgumentParser(description="字体体检报告")
    ap.add_argument("font")
    ap.add_argument("--text", default=None, help="检测这段文字是否缺字")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sample", action="store_true")
    a = ap.parse_args()
    try:
        report(a.font, a.text, a.sample, a.json)
    except Exception as e:
        print(f"读取失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
