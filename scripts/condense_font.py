#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
condense_font.py —— 字体横向收窄工具

只压缩 x 轴、y 轴保持不动：字变「窄长」，而不是整体压扁。
同时同步修正字宽（advance width）、字边距、全局度量与元信息，
让新字体在剪辑软件 / 设计软件 / 网页里都能被正确排版。

用法:
    python3 condense_font.py 输入.ttf 输出.ttf --scale 0.8
    python3 condense_font.py 输入.ttf 输出.ttf --scale 0.75 --name "MyFont Narrow"
"""

import argparse
import math
import os
import sys

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
from fontTools.ttLib.tables.ttProgram import Program
from fontTools.pens.transformPen import TransformPen


def width_class(sx):
    """按压缩比例给出 OS/2 usWidthClass（1 最窄 ~ 5 正常）。"""
    if sx >= 0.90:
        return 4   # Semi-condensed
    if sx >= 0.78:
        return 3   # Condensed
    if sx >= 0.68:
        return 2   # Extra-condensed
    return 1       # Ultra-condensed


def _compose_component_transform(t, sx, m=0.0):
    """复合字形：把横向缩放+倾斜并到组件变换矩阵的左侧（M · T）。
    M = [[sx, m], [0, 1]]；m = tan(倾斜角)，实现 x' = sx*x + m*y 的伪斜体效果。"""
    a, b, c, d, e, f = t
    return (a * sx + b * m, b, c * sx + d * m, d, e * sx + f * m, f)


def _private_for(top, gid, fallback_global):
    """取 glyph 所属 FontDict 的 Private。CID-keyed CFF(中文大字库) 的 Private 在 FDArray 里。"""
    priv = getattr(top, "Private", None)
    if priv is not None:
        return priv, getattr(top, "GlobalSubrs", None)
    fdarray = getattr(top, "FDArray", None)
    fdselect = getattr(top, "FDSelect", None)
    if fdarray and fdselect is not None:
        try:
            fdi = fdselect[gid] if hasattr(fdselect, "__getitem__") else fdselect(gid)
            fd = fdarray[fdi]
            return (getattr(fd, "Private", None),
                    getattr(fd, "GlobalSubrs", fallback_global))
        except Exception:
            pass
    return None, fallback_global


def _instantiate_vf(font, spec, log):
    """可变字体：先实例化成静态字体再收窄。
    否则 gvar 里的字形增量不会随基础轮廓缩放，切到非默认字重就会变形。"""
    from fontTools.varLib import instancer
    if spec:
        axes = {}
        for kv in spec.split(","):
            k, v = kv.split("=")
            axes[k.strip()] = float(v)
    else:
        axes = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
    log(f"  检测到可变字体，先实例化到静态: "
        + ", ".join(f"{k}={v:g}" for k, v in axes.items()))
    return instancer.instantiateVariableFont(
        font, axes, inplace=True, updateFontNames=False)


def _condense_cff(font, sx, log, slant=0):
    """OpenType/CFF 轮廓：用 T2CharStringPen 重建 charstring。支持 CID-keyed。"""
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    m = math.tan(math.radians(slant))
    cff = font["CFF "]
    top = cff.cff.topDictIndex[0]
    gl_global = getattr(top, "GlobalSubrs", None)
    charstrings = top.CharStrings
    hmtx = font["hmtx"]
    order = font.getGlyphOrder()

    done = skipped = 0
    for gid, name in enumerate(order):
        try:
            cs = charstrings[name]
        except (KeyError, TypeError):
            continue
        private, global_subrs = _private_for(top, gid, gl_global)
        if private is None:
            skipped += 1
            continue
        try:
            aw = hmtx[name][0]
            pen = T2CharStringPen(aw, None)
            # 组合：x 缩放 sx + x 随 y 倾斜（m = tanθ）
            cs.draw(TransformPen(pen, (sx, 0, m, 1, 0, 0)))
            new_cs = pen.getCharString(private, global_subrs)
            new_cs.private = private          # 不补上保存时会崩
            new_cs.globalSubrs = global_subrs
            new_cs.width = aw
            charstrings[name] = new_cs
            done += 1
        except Exception as e:
            skipped += 1
            if skipped <= 2:
                log(f"  ! CFF 字形 {name} 变换失败: {e}")
    log(f"  CFF 轮廓: 已变换 {done} 个" + (f"，跳过 {skipped} 个" if skipped else ""))
    if done == 0:
        raise SystemExit("CFF 变换全部失败，该字体结构不受支持（建议先转 TTF 再收窄）")
    return done


def _sanitize_cmap(font, log):
    """把 cmap 里可能 16 位溢出的 format 4 子表移除或转成 format 12。
    大字符集字体（CJK/彩色字体/表情）在保存时常因 format 4 的 glyph ID 或
    idRangeOffset 超过 65535 而报 struct.error。format 12 用 32 位，无此限制。"""
    if "cmap" not in font:
        return
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
    cmap = font["cmap"]
    has_f12 = any(st.format == 12 for st in cmap.tables)
    new_tables = []
    changed = 0
    for st in cmap.tables:
        if st.format != 4:
            new_tables.append(st)
            continue
        if has_f12:
            # 已有 format 12，format 4 可以直接丢
            changed += 1
            continue
        # 没有 format 12 时，把 format 4 转成 12，避免保存时 16 位溢出
        try:
            nst = CmapSubtable.newSubtable(12)
            nst.platformID = st.platformID
            nst.platEncID = st.platEncID
            nst.language = getattr(st, "language", 0)
            nst.cmap = st.cmap
            new_tables.append(nst)
            changed += 1
        except Exception as e:
            log(f"  ! 无法转换 cmap format 4 子表：{e}")
            new_tables.append(st)
    if changed:
        cmap.tables = new_tables
        log(f"  处理 {changed} 个 cmap format 4 子表（移除/转 format 12），避免大字体保存溢出")


def _finish_and_save(font, sx, dst, family, note, log, slant=0):
    """CFF / glyf 共用的收尾：度量、命名、保存。"""
    m = math.tan(math.radians(slant))
    hmtx = font["hmtx"]
    for name in list(hmtx.metrics):
        aw, lsb = hmtx.metrics[name]
        hmtx.metrics[name] = (int(round(aw * sx)), int(round(lsb * sx)))
    hhea = font["hhea"]
    hhea.advanceWidthMax = int(round(hhea.advanceWidthMax * sx))
    hhea.minLeftSideBearing = int(round(hhea.minLeftSideBearing * sx))
    hhea.minRightSideBearing = int(round(hhea.minRightSideBearing * sx))
    os2 = font["OS/2"]
    if hasattr(os2, "xAvgCharWidth"):
        os2.xAvgCharWidth = int(round(os2.xAvgCharWidth * sx))
    os2.usWidthClass = width_class(sx)
    head = font["head"]
    # 倾斜会让 x 边界随 y 偏移：x' = sx*x + m*y
    head.xMin = int(round(head.xMin * sx + m * head.yMin))
    head.xMax = int(round(head.xMax * sx + m * head.yMax))
    _sanitize_cmap(font, log)
    if family:
        # PostScript 名（nameID 6）只允许 ASCII 可见字符，且有 63 字节上限。
        # 中文名/空格/括号写进去会导致部分系统装不上，这里先净化。
        ps = "".join(c for c in family if 33 <= ord(c) < 127 and c not in "[](){}<>/%")
        if not ps or ps[:1].isdigit():
            # 名字全是中文/符号时，退回一个安全的 ASCII 名，避免装不上
            ps = "Condensed-" + str(abs(hash(family)) % 100000)
        ps = ps[:63]
        for rec in font["name"].names:
            try:
                if rec.nameID in (1, 4, 16):
                    rec.string = family
                elif rec.nameID == 6:
                    rec.string = ps
                elif rec.nameID == 3:
                    rec.string = f"{family} : condensed"
                elif rec.nameID == 0 and note:
                    rec.string = rec.toUnicode().rstrip() + " " + note
            except Exception:
                continue
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    font.save(dst)
    log(f"  ✓ 已生成: {dst}  ({os.path.getsize(dst)/1024/1024:.2f} MB)")
    return dst


def condense(src, dst, sx, family=None, keep_hinting=False, note=None,
             quiet=False, instance=None, slant=0):
    def log(*a):
        if not quiet:
            print(*a)

    # 防呆：源和目标同路径会把输入覆盖掉，直接拒绝
    if os.path.abspath(src) == os.path.abspath(dst):
        raise SystemExit("输入和输出不能是同一个文件，换个输出路径（否则原字体被覆盖）")
    if not os.path.exists(src):
        raise SystemExit(f"找不到输入字体: {src}")

    try:
        font = TTFont(src)
    except Exception as e:
        raise SystemExit(f"这个文件不是有效的字体（{e}）: {src}")
    if "fvar" in font:
        font = _instantiate_vf(font, instance, log)
        # 实例化后可能变成 CFF 或 glyf，重新判断
    if "glyf" not in font:
        if "CFF " not in font:
            raise SystemExit(f"无法识别的字体格式: {src}")
        log("  检测到 OpenType/CFF 轮廓，走 CFF 分支")
        if dst.lower().endswith(".ttf"):
            log("  ⚠ 警告：源是 OTF(CFF)，即便输出文件名写成 .ttf，"
                "生成的仍是 OTF 风味（sfnt 头为 OTTO），Windows/部分软件会拒装。\n"
                "     建议：① 输出改为 .otf；或 ② 生成后再跑 otf2ttf.py 转成真正的 TTF。")
        _condense_cff(font, sx, log, slant=slant)
        return _finish_and_save(font, sx, dst, family, note, log, slant=slant)

    glyf = font["glyf"]
    glyph_order = font.getGlyphOrder()
    m = math.tan(math.radians(slant))

    # ---------- 1. 字形轮廓：x 按比例缩放 + 可选倾斜，y 不动 ----------
    n_simple = n_comp = n_hint = 0
    for name in glyph_order:
        g = glyf[name]

        # 清掉字形级 hinting 指令（缩放后网格对齐已失效，留着反而渲染错乱）
        if not keep_hinting and getattr(g, "program", None) is not None:
            try:
                if g.program and len(g.program.instructions):
                    n_hint += 1
            except Exception:
                pass
            g.program = Program()

        if g.numberOfContours == 0:
            continue

        if g.isComposite():
            n_comp += 1
            for comp in g.components:
                if hasattr(comp, "transform"):
                    comp.transform = _compose_component_transform(comp.transform, sx, m)
            if hasattr(g, "recalcBounds"):
                g.recalcBounds(glyf)
            continue

        n_simple += 1
        coords = g.coordinates
        if coords is None:
            continue
        # x 缩放 sx 并加上 y*m 的倾斜；y 保持不动
        g.coordinates = GlyphCoordinates(
            [(int(round(x * sx + y * m)), y) for x, y in coords]
        )
        if hasattr(g, "recalcBounds"):
            g.recalcBounds(glyf)

    log(f"  轮廓: 简单字形 {n_simple} 个, 复合字形 {n_comp} 个, 清除字形指令 {n_hint} 个")

    # ---------- 2. 字宽与左边距 ----------
    hmtx = font["hmtx"]
    widths = {}
    for name in glyph_order:
        aw, lsb = hmtx[name]
        widths[name] = (int(round(aw * sx)), int(round(lsb * sx)))
    hmtx.metrics.update(widths)

    # ---------- 3. 水平布局度量 ----------
    hhea = font["hhea"]
    hhea.advanceWidthMax = int(round(hhea.advanceWidthMax * sx))
    hhea.minLeftSideBearing = int(round(hhea.minLeftSideBearing * sx))
    hhea.minRightSideBearing = int(round(hhea.minRightSideBearing * sx))

    # ---------- 4. OS/2 ----------
    os2 = font["OS/2"]
    if hasattr(os2, "xAvgCharWidth"):
        os2.xAvgCharWidth = int(round(os2.xAvgCharWidth * sx))
    os2.usWidthClass = width_class(sx)
    for attr in ("sTypoAscender", "sTypoDescender", "sTypoLineGap",
                 "usWinAscent", "usWinDescent"):
        pass  # 纵向度量不变，保持行高与基线稳定

    # ---------- 5. head 包围盒（按真实字形重新算，倾斜后更准确） ----------
    head = font["head"]
    x_min = y_min = x_max = y_max = None
    for name in glyph_order:
        g = glyf[name]
        if g.numberOfContours == 0:
            continue
        if hasattr(g, "recalcBounds"):
            g.recalcBounds(glyf)
        try:
            gxmin, gymin, gxmax, gymax = g.xMin, g.yMin, g.xMax, g.yMax
        except Exception:
            continue
        if x_min is None or gxmin < x_min:
            x_min = gxmin
        if y_min is None or gymin < y_min:
            y_min = gymin
        if x_max is None or gxmax > x_max:
            x_max = gxmax
        if y_max is None or gymax > y_max:
            y_max = gymax
    if x_min is not None:
        head.xMin, head.yMin, head.xMax, head.yMax = x_min, y_min, x_max, y_max

    # ---------- 6. 移除字节码 hinting（fpgm/prep/cvt 在无 fpgm 时会让某些渲染器出错） ----------
    if not keep_hinting:
        removed = [t for t in ("fpgm", "prep", "cvt ") if t in font]
        for t in removed:
            del font[t]
        if removed:
            log(f"  已移除 hinting 表: {', '.join(x.strip() for x in removed)}")
        # 同步 head.flags：清掉「需要指令」相关位
        head.flags &= ~0x0008  # 位3: 指令可能改变 advance width

    # ---------- 7. 改名字，避免和原字体冲突 ----------
    if family:
        # PostScript 名（nameID 6）规范只允许 ASCII 可见字符，且上限 63 字节。
        # 直接塞中文/空格/括号会导致部分系统（尤其 Windows、某些 App）装不上或显示异常。
        ps_name = "".join(
            c for c in family if 33 <= ord(c) < 127 and c not in "[](){}<>/%")
        if not ps_name or ps_name[:1].isdigit():
            ps_name = "Condensed-" + str(abs(hash(family)) % 100000)
        ps_name = ps_name[:63]
        for rec in font["name"].names:
            nid = rec.nameID
            try:
                old = rec.toUnicode()
            except Exception:
                continue
            if nid in (1, 4, 16):
                rec.string = family
            elif nid == 3:
                rec.string = f"{family} : {old.split(':')[-1].strip()}"
            elif nid == 6:
                rec.string = ps_name
            elif nid == 0 and note:
                rec.string = f"{old} {note}"
        font["name"].names = font["name"].names

    # ---------- 8. 保存 ----------
    _sanitize_cmap(font, log)
    if "maxp" in font and hasattr(font["maxp"], "recalc"):
        try:
            font["maxp"].recalc(font)
        except Exception:
            pass

    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    font.save(dst)
    log(f"  ✓ 已生成: {dst}  ({os.path.getsize(dst)/1024/1024:.2f} MB)")
    return dst


def main():
    ap = argparse.ArgumentParser(description="把字体整体横向收窄（变窄长，不变扁）")
    ap.add_argument("src", help="输入字体文件路径")
    ap.add_argument("dst", help="输出字体文件路径")
    ap.add_argument("--scale", type=float, default=0.8,
                    help="横向缩放比例，0.8 表示宽度变为原来的 80%%，默认 0.8")
    ap.add_argument("--name", default=None, help="新字体家族名，如 'ChosunKg Narrow'")
    ap.add_argument("--keep-hinting", action="store_true",
                    help="保留 hinting 指令（一般不建议，缩放后指令已失效）")
    ap.add_argument("--note", default=None, help="追加到版权信息里的说明文字")
    ap.add_argument("--instance", default=None,
                    help="可变字体先实例化成静态，如 wght=900 或 wght=700,wdth=85；"
                         "缺省用各轴默认值")
    ap.add_argument("--slant", type=float, default=0,
                    help="伪斜体倾斜角（度），0~20，实现 x 随 y 倾斜；默认 0")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not 0.4 <= args.scale <= 1.0:
        sys.exit("scale 应在 0.4 ~ 1.0 之间")
    if not -30 <= args.slant <= 30:
        sys.exit("slant 应在 -30 ~ 30 度之间")

    condense(args.src, args.dst, args.scale,
             family=args.name, keep_hinting=args.keep_hinting,
             note=args.note, quiet=args.quiet, instance=args.instance,
             slant=args.slant)


if __name__ == "__main__":
    main()
