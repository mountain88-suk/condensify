#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_missing.py —— 给目标字体补齐缺失的汉字

字形来源（默认）：Noto Sans SC Black（SIL OFL 1.1，允许修改与再分发）
处理流程：补字源(CFF/OTF) → TrueType 轮廓 → 按字面比例自动对齐目标字体 → 写入
结果：一个字体文件，目标字体原本缺的汉字由补字源补齐，不再回退到系统字体。

用法:
    python3 fill_missing.py 目标.ttf 补字源.otf 输出.ttf [--scale 0.70]
"""

import argparse
import os
import time

from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen

# 对齐参数在运行时自动测量（measure_face），不依赖硬编码常量。

# 补字范围：CJK 基本区 / 扩展A / 兼容区 / CJK标点 / 全角符号
RANGES = [(0x2010, 0x2027), (0x3000, 0x303F), (0x3400, 0x4DBF),
          (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0xFF01, 0xFF60)]

NOTO_COPYRIGHT = ("Missing glyphs filled with Noto Sans SC "
                  "(SIL OFL 1.1, Copyright 2022 The Noto Sans SC Project Authors, "
                  "https://github.com/notofonts/noto-cjk).")

# 测量字面对齐用的样字：选简繁同形、多数字体都有的常用汉字
PROBE_CHARS = "山水天力大日月口木火土人心手目白田甲由申石竹米舟行衣西耳自舌弓干工上下中"


def _sanitize_ps_name(family):
    """PostScript 名(nameID 6)只认 ASCII 可见字符、限 63 字节。
    中文/空格/括号写进去会导致 Windows 或某些 App 装不上，这里净化。"""
    ps = "".join(c for c in (family or "")
                 if 33 <= ord(c) < 127 and c not in "[](){}<>/%")
    if not ps or ps[:1].isdigit():
        ps = "Condensed-" + str(abs(hash(family)) % 100000)
    return ps[:63]


def measure_face(font, cmap, chars):
    """测量一组汉字的字面：平均 高 / 宽 / 中心点。跨字体对齐用。"""
    from fontTools.pens.boundsPen import BoundsPen
    gs = font.getGlyphSet()
    hs, ws, cxs, cys = [], [], [], []
    for ch in chars:
        gn = cmap.get(ord(ch))
        if gn is None:
            continue
        try:
            bp = BoundsPen(gs); gs[gn].draw(bp)
        except Exception:
            continue
        if not bp.bounds:
            continue
        x0, y0, x1, y1 = bp.bounds
        if x1 - x0 <= 0 or y1 - y0 <= 0:
            continue
        ws.append(x1 - x0); hs.append(y1 - y0)
        cxs.append((x0 + x1) / 2); cys.append((y0 + y1) / 2)
    if len(hs) < 4:
        return None
    return {"n": len(hs), "height": sum(hs) / len(hs), "width": sum(ws) / len(ws),
            "cx": sum(cxs) / len(cxs), "cy": sum(cys) / len(cys)}


def pick_probe(tgt_cmap, src_cmap, limit=24):
    """挑两款字体都有的汉字作测量样本。"""
    common = [c for c in PROBE_CHARS if ord(c) in tgt_cmap and ord(c) in src_cmap]
    if len(common) < 8:
        extra = [chr(c) for c in sorted(set(tgt_cmap) & set(src_cmap))
                 if 0x4E00 <= c <= 0x9FFF]
        common += extra[:limit * 3]
    return common[:limit]


def fill(target_path, source_path, out_path, scale=0.70, family=None,
         copyright_note=None, quiet=False, measure_path=None):
    def log(*a):
        if not quiet:
            print(*a)

    for p, lab in ((target_path, "目标字体"), (source_path, "补字源"),
                   (measure_path, "测量字体")):
        if p and not os.path.exists(p):
            raise SystemExit(f"找不到{lab}: {p}")
    for a, b in ((target_path, out_path), (source_path, out_path)):
        if os.path.abspath(a) == os.path.abspath(b):
            raise SystemExit("输入和输出不能是同一个文件（否则原字体被覆盖）")

    try:
        tgt = TTFont(target_path)
        src = TTFont(source_path)
    except Exception as e:
        raise SystemExit(f"字体文件打不开（{e}）")
    src_cmap = src.getBestCmap()
    tgt_cmap = tgt.getBestCmap()

    # 缺字为零时没有补的必要，提前返回，避免白等
    need = [c for c in src_cmap if c not in tgt_cmap]
    if not need:
        log("  目标字体已覆盖补字源的全部码位，无需补字")
        return None
    log(f"  待补码位: {len(need)} 个")

    # ---------- 自动测量字面对齐参数（不再依赖硬编码常量） ----------
    # 若补字源是子集化版本，可能已不含测量样字，此时用 --measure-source 指定完整字体
    meas = TTFont(measure_path) if measure_path else src
    meas_cmap = meas.getBestCmap() if measure_path else src_cmap
    probe = pick_probe(tgt_cmap, meas_cmap)
    tm = measure_face(tgt, tgt_cmap, probe)
    sm = measure_face(meas, meas_cmap, probe)
    if not tm or not sm:
        raise SystemExit(
            "无法自动对齐字面：两款字体缺少足够的共同汉字。\n"
            "  常见原因：补字源被子集化过，样字已被剔除。\n"
            "  解决：补字源改用完整字体，或用 --measure-source 指定完整字体仅用于测量。")
    if measure_path:
        log(f"测量源: {measure_path}（{len(probe)} 个样字）")
    sy = tm["height"] / sm["height"]      # 纵向：源字面高 → 目标字面高
    sx = tm["width"] / sm["width"]        # 横向：目标已是窄版，直接对齐其字面宽
    dx = tm["cx"] - sm["cx"] * sx
    dy = tm["cy"] - sm["cy"] * sy

    # 目标字宽：直接沿用目标字体里汉字的 advance
    adv = None
    for ch in "山水天一工":
        if ord(ch) in tgt_cmap:
            adv = tgt["hmtx"][tgt_cmap[ord(ch)]][0]
            break
    if adv is None:
        adv = int(round(tgt["head"].unitsPerEm * scale))

    log(f"对齐样字 {len(probe)} 个: 目标字面 高{tm['height']:.0f}/宽{tm['width']:.0f}"
        f" 中心({tm['cx']:.0f},{tm['cy']:.0f})")
    log(f"              源字面 高{sm['height']:.0f}/宽{sm['width']:.0f}"
        f" 中心({sm['cx']:.0f},{sm['cy']:.0f})")
    log(f"变换: scaleX={sx:.4f} scaleY={sy:.4f} 平移=({dx:.1f}, {dy:.1f}) 字宽={adv}")

    src_gs = src.getGlyphSet()
    tgt_gs = tgt.getGlyphSet()
    glyf, hmtx = tgt["glyf"], tgt["hmtx"]
    order = list(tgt.getGlyphOrder())   # 必须复制：glyf 会自己维护一份同名列表
    used = set(order)

    todo = [cp for cp in sorted(src_cmap)
            if cp not in tgt_cmap and any(a <= cp <= b for a, b in RANGES)]
    log(f"待补码位: {len(todo)}")

    cmap_tables = [t for t in tgt["cmap"].tables
                   if t.platformID == 3 and t.platEncID == 1]
    t0 = time.time()
    added = 0
    for i, cp in enumerate(todo, 1):
        sgname = src_cmap[cp]
        gname = "uni%04X" % cp
        n = 0
        while gname in used:
            n += 1
            gname = "uni%04X.%d" % (cp, n)

        pen = TTGlyphPen(tgt_gs)
        tpen = TransformPen(pen, (sx, 0, 0, sy, dx, dy))
        cu = Cu2QuPen(tpen, max_err=1.0, reverse_direction=True)
        src_gs[sgname].draw(cu)
        g = pen.glyph()

        if g.numberOfContours > 0:
            g.recalcBounds(glyf)
            lsb = g.xMin
        else:
            lsb = 0

        glyf[gname] = g
        order.append(gname)
        used.add(gname)
        hmtx[gname] = (adv, lsb)
        for t in cmap_tables:
            if cp <= 0xFFFF:
                t.cmap[cp] = gname
        added += 1

        if i % 5000 == 0:
            log(f"  ...{i}/{len(todo)}  用时 {time.time()-t0:.0f}s")

    tgt.setGlyphOrder(order)
    glyf.glyphOrder = order          # 同步给 glyf 表，否则 maxp 重算会断言失败
    assert len(glyf.glyphs) == len(order), (len(glyf.glyphs), len(order))
    log(f"已补字形: {added} 个，用时 {time.time()-t0:.1f}s")

    # ---------- 全局度量重算 ----------
    xMin = yMin = 1 << 30
    xMax = yMax = -(1 << 30)
    for gname in order:
        g = glyf[gname]
        if g.numberOfContours > 0:
            xMin = min(xMin, g.xMin); yMin = min(yMin, g.yMin)
            xMax = max(xMax, g.xMax); yMax = max(yMax, g.yMax)
    if xMax > xMin:
        head = tgt["head"]
        head.xMin, head.yMin, head.xMax, head.yMax = xMin, yMin, xMax, yMax
        log(f"整体包围盒: ({xMin}, {yMin}) ~ ({xMax}, {yMax})")

    hhea = tgt["hhea"]
    hhea.numberOfHMetrics = len(order)

    allw = [hmtx[g][0] for g in order if g in hmtx.metrics]
    if allw:
        tgt["OS/2"].xAvgCharWidth = int(round(sum(allw) / len(allw)))

    # ---------- 版权与命名 ----------
    note = copyright_note or NOTO_COPYRIGHT
    for rec in tgt["name"].names:
        if rec.nameID == 0:
            try:
                old = rec.toUnicode()
            except Exception:
                continue
            if note.split("(")[0].strip()[:12] not in old:
                rec.string = old.rstrip() + "  " + note
        elif rec.nameID in (1, 3, 4, 6, 16) and family:
            try:
                old = rec.toUnicode()
            except Exception:
                continue
            if rec.nameID == 6:
                rec.string = _sanitize_ps_name(family)
            elif rec.nameID == 3:
                rec.string = f"{family} : filled with Noto Sans SC"
            else:
                rec.string = family

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    tgt.save(out_path)
    log(f"✓ {out_path}  ({os.path.getsize(out_path)/1024/1024:.2f} MB, {len(order)} 字形)")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="给目标字体补齐缺失的汉字")
    ap.add_argument("target", help="目标字体（窄版 TTF/OTF）")
    ap.add_argument("source", help="补字源字体（默认 Noto Sans SC，OFL）")
    ap.add_argument("out", help="输出文件")
    ap.add_argument("--scale", type=float, default=0.70, help="仅用于兜底推算字宽")
    ap.add_argument("--name", default=None, help="新字体名")
    ap.add_argument("--copyright-note", default=None, help="追加到版权字段的说明")
    ap.add_argument("--measure-source", default=None,
                    help="仅用于字面测量的完整字体（补字源是子集时用）")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    fill(a.target, a.source, a.out, a.scale, a.name,
         a.copyright_note, a.quiet, a.measure_source)


if __name__ == "__main__":
    main()
