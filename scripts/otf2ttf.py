#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
otf2ttf.py —— CFF(OTF) 轮廓转 TrueType(TTF) 轮廓

什么情况下需要：
  · 目标软件只认 TTF（部分剪辑软件 / 老系统 / 某些 App 内置渲染器）
  · 要把 OTF 字体合并进一个 TTF 目标字体

代价：三次贝塞尔转二次（Cu2Qu），有极小误差（默认 1/1000 em，肉眼不可见），
      且会丢失 CFF 的 subrs 压缩，文件通常变大。

用法:
    python3 otf2ttf.py 输入.otf 输出.ttf [--max-err 1.0]
"""

import argparse
import os
import sys
import time

from fontTools.ttLib import TTFont, newTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen


def convert(src, dst, max_err=1.0, quiet=False):
    def log(*a):
        if not quiet:
            print(*a)

    if os.path.abspath(src) == os.path.abspath(dst):
        raise SystemExit("输入和输出不能是同一个文件（否则原字体被覆盖）")
    if not os.path.exists(src):
        raise SystemExit(f"找不到输入字体: {src}")
    try:
        font = TTFont(src)
    except Exception as e:
        raise SystemExit(f"这个文件不是有效的字体（{e}）: {src}")
    if "glyf" in font:
        raise SystemExit(f"已经是 TrueType 轮廓，无需转换: {src}")
    if "CFF " not in font:
        raise SystemExit(f"不是 CFF 字体: {src}")

    order = font.getGlyphOrder()
    gs = font.getGlyphSet()

    glyf = newTable("glyf")
    glyf.glyphOrder = list(order)
    glyf.glyphs = {}

    t0 = time.time()
    for i, name in enumerate(order, 1):
        pen = TTGlyphPen(gs)
        gs[name].draw(Cu2QuPen(pen, max_err, reverse_direction=True))
        glyf[name] = pen.glyph()
        if i % 8000 == 0:
            log(f"  ...{i}/{len(order)}  用时 {time.time()-t0:.0f}s")

    font["glyf"] = glyf
    # loca（字形位置索引）必须显式建表，否则 fontTools 不会写，渲染器会报缺表
    font["loca"] = newTable("loca")
    # 关键：sfnt 版本标签必须从 OTTO(CFF) 改成 00010000(TrueType)，
    # 否则文件头还是 OTTO，渲染器（FreeType/PIL/系统）会直接拒绝加载。
    font.sfntVersion = "\x00\x01\x00\x00"
    del font["CFF "]
    for t in ("VORG",):          # CFF 专有表，TTF 里没意义
        if t in font:
            del font[t]

    # maxp 从 CFF 版(0.5) 重建为 TrueType 版(1.0)
    # 直接改 tableVersion 会缺 TrueType 专有字段（maxZones 等），必须换张新表
    font["maxp"] = maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    # TrueType 专有字段，recalc 不会填，必须手动给（无 hinting 所以大多为 0）
    maxp.maxZones = 2
    maxp.maxTwilightPoints = 0
    maxp.maxStorage = 0
    maxp.maxFunctionDefs = 0
    maxp.maxInstructionDefs = 0
    maxp.maxStackElements = 0
    maxp.maxSizeOfInstructions = 0
    maxp.maxComponentElements = 0
    maxp.maxComponentDepth = 0
    maxp.numGlyphs = len(order)
    # 长格式 loca（4 字节偏移）：短格式最多只能表达 128KB 的 glyf 数据，
    # 中文字体远超这个量，必须用 1。
    font["head"].indexToLocFormat = 1

    for name in order:
        g = glyf[name]
        if g.numberOfContours > 0:
            g.recalcBounds(glyf)

    # 补上 maxPoints / maxContours / maxComposite* 等由 glyf 统计出来的字段
    maxp.recalc(font)

    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    font.save(dst)
    log(f"✓ {dst}  ({os.path.getsize(dst)/1024/1024:.2f} MB, {len(order)} 字形, "
        f"用时 {time.time()-t0:.0f}s)")
    return dst


def main():
    ap = argparse.ArgumentParser(description="CFF(OTF) 转 TrueType(TTF)")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--max-err", type=float, default=1.0,
                    help="曲线转换最大误差（em 单位），越小越精确但点越多、文件越大")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    convert(a.src, a.dst, a.max_err, a.quiet)


if __name__ == "__main__":
    main()
