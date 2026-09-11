# Condensify · 字体收窄与补字工具

把任意开源字体**横向收窄**（变窄长，不是压扁）、**补齐缺失汉字**，生成可直接安装的 TTF/OTF。

给剪辑字幕、竖排标题、空间紧张的排版用——改一次字体，以后直接换字体就行，不用再逐字抠图手动拉扁。

```
原版：山水每天努力生活   ← 字宽 1000
60% ：山水每天努力生活   ← 字宽 600，高度一模一样
```

---

## 为什么是"收窄"而不是"压扁"

只缩放 x 轴，y 轴一动不动：

- 字**变窄长**，不是变矮变胖
- 横笔画粗细不变，竖笔画按比例变细
- 行高、基线完全不动，不会打乱你已有的排版

因为字距（advance width）也同步缩放，所以 CSS `scaleX` 预览和真实字体渲染**逐像素等价**——可以先用网页滑块确认比例，再动手生成。

---

## 安装

```bash
pip install fonttools brotli
python3 -c "import fontTools; print(fontTools.version)"   # 需要 >= 4.40
```

---

## 三个脚本

### 1. `font_report.py` — 拿到字体先看清楚

```bash
python3 scripts/font_report.py 字体.ttf --text "你会用到的文字"
```

一次输出：轮廓格式（glyf / CFF）、字形数、各区覆盖率、**简体可用度**、汉字字面度量、**许可自动识别**、改造建议。

### 2. `condense_font.py` — 收窄

```bash
python3 scripts/condense_font.py 输入.ttf 输出.ttf --scale 0.60 --name "Narrow Sans SC 60"
```

- `--scale`：横向比例，`0.60` = 宽度变 60%，**高度完全不变**
- `--name`：新字体名（**必须改**，避免与原字体冲突）
- 支持 TTF(glyf) 和 OTF(CFF)，OTF 自动走 CFF 分支（含 CID-keyed 结构）

自动处理的细节：字宽、左右边距、OS/2 宽度分级、head 包围盒、清除失效的 hinting。

### 3. `fill_missing.py` — 补齐缺字

```bash
python3 scripts/fill_missing.py 窄版.ttf NotoSansSC-Black.otf 输出-SC.ttf --name "MyFont Narrow 60 SC"
```

- 自动测量两款字体的汉字字面（高 / 宽 / 中心），算出对齐变换，补进来的字与原文**融为一体**
- 只补目标字体**缺的**码位，已有字形一个不动
- 补字源是 CFF 时自动做 CFF → TrueType 轮廓转换
- 补字源若是子集（量不出字面），加 `--measure-source 完整字体.otf`

### 4. `otf2ttf.py` — OTF 转 TTF（可选）

```bash
python3 scripts/otf2ttf.py 窄版.otf 窄版.ttf
```

当源是 OTF（CFF 轮廓）而你需要 **TTF**（某些剪辑软件 / 老系统只认 TTF）时，
`condense_font.py` 的 CFF 分支只能输出 OTF，再用本脚本转成 TTF：

```
源.otf  →  condense_font.py  →  窄版.otf  →  otf2ttf.py  →  窄版.ttf
```

内部做：三次贝塞尔 → 二次（误差 < 1/1000 em，肉眼不可见）、sfnt 头 `OTTO` → `00010000`、
重建 TrueType 版 maxp、`loca` 长格式。代价：文件变大、可能略微丢精度。

---

## 典型工作流

```bash
# ① 体检：确认格式、缺字、许可
python3 scripts/font_report.py myfont.ttf --text "山每天都在努力生活"

# ② 收窄：一次多做几档挑
for s in 85 80 75 70 65 60; do
  python3 scripts/condense_font.py myfont.ttf out/narrow-$s.ttf \
    --scale 0.$s --name "MyFont Narrow $s"
done

# ③ 补字（简体不全时）
python3 scripts/fill_missing.py out/narrow-60.ttf NotoSansSC-Black.otf \
  out/narrow-60-SC.ttf --name "MyFont Narrow 60 SC"

# ④ 验证
python3 scripts/font_report.py out/narrow-60-SC.ttf --text "山每天都在努力生活啊"
```

`examples/batch.sh` 里有一个可直接改用的批量脚本。

---

## 网页工具（零安装、字体不出浏览器）

`web/index.html` 是一个纯前端工具：上传字体 → 拖滑块选宽度 → 一键下载窄版。
底层用 Pyodide 在浏览器里跑 fontTools，与命令行脚本同一套逻辑，**字体全程不离开你的电脑**。

功能：
- 上传 .ttf / .otf，实时 CSS `scaleX` 预览（与真实渲染逐像素等价）
- 滑块选 60%–100% 宽度
- 自动体检：简体可用度、缺字、许可（含 OFL 保留字体名警告）
- 可选「补齐缺失简体汉字」（下载 Noto Sans SC 作补字源）
- 一键下载 TTF / OTF

> ⚠️ 必须用 http 服务打开（本地起服务或部署到静态托管），**不能双击 `file://` 直接打开**——
> 因为页面要按需加载同目录下的 `scripts/` 脚本与 Pyodide 运行时。
> 本地预览：`python -m http.server` 后访问 `http://localhost:8000/web/`。

---

## ⚠️ 许可：这个必须先看

工具本身是 MIT，但**你改造的字体受它自己的许可约束**——这是你的责任，不是工具的。

`font_report.py` 会扫描字体内嵌的许可信息，但请以下面为准：

| 原字体许可 | 能改吗 | 能分发吗 | 例子 |
|---|---|---|---|
| **SIL OFL / Apache / 公共领域** | ✅ | ✅ 需保留许可文件 | 思源黑体、Noto 系列 |
| **厂商"免费商用"** | ⚠️ 多数禁止修改 | ✅ 只能原样分发 | 阿里巴巴普惠体、HarmonyOS Sans |
| **商业授权** | ❌ | ❌ | 方正、汉仪 |

### OFL 的三条铁律

1. **保留字体名（RFN）不能用于衍生版**
   例：Noto Sans SC 的 RFN 是 `'Source'`（Adobe 思源系列），所以衍生版不能叫 "Source ×××"。
   实践建议：起个全新的名字，别让人误以为是官方版本。
2. **再分发必须附带 OFL 许可文件**
3. **不能单独卖字体文件本身**
   但可以卖包含字体的产品（软件、书、模板包、T 恤），这点 OFL 明确允许。

### 关于"自用就没事吗"

"自用"不是法律豁免，只是实际风险低。边界在**是否对外**：

- 自己电脑装着剪自己的视频 → 安全
- 发到网上 / 给客户 / 放进产品 → 已经越过原条款，哪怕没收钱也算分发

要分享、要商用、要做交付，就选 OFL 字体走全流程，才真正没有后顾之忧。

---

## 作为 AI Agent Skill 使用

根目录的 `SKILL.md` 是给 AI Agent（CodeBuddy / Claude Code 等）看的技能定义。
放到你的 skills 目录后，直接说「**把这个字体变窄到 70%**」并丢文件过去，Agent 会自动完成体检 → 许可核查 → 收窄 → 补字 → 验证。

---

## 踩坑记录

都是真踩过的，写下来省得你再踩一遍：

1. **CDN 会截断大字体** — jsdelivr / ghproxy 下 8MB+ 文件会静默截断，头看着正常但表是坏的。先 `curl -I` 拿 `Content-Length`，再并行分段 `curl -r` 下载后 `cat` 合并。
2. **`getGlyphOrder()` 返回内部引用** — 直接 append 会让字形名被添加两次，`maxp` 重算时断言失败。必须 `list(...)` 复制。
3. **CFF 的 Private 在 FDArray 里** — 中文大字库是 CID-keyed CFF，`top.Private` 为 None，要从 `FDSelect[gid] → FDArray[i].Private` 取；新建的 charstring 必须手动补 `private` / `globalSubrs`。
4. **缩放后 hinting 全废** — `fpgm` / `prep` / `cvt ` 和字形级 program 都要清；字形 program 不能设 `None`（compile 报错），要设成空 `Program()`。
5. **`lsb` 必须等于字形 `xMin`** — CJK 字体通行规则，补字时照做才不会排版错位。
6. **补字源别预先子集化** — 子集里没有测量样字，自动对齐会失败。
7. **别指望"缺字回退"** — 剪映 / Premiere 走系统固定回退链，**无法自定义 fallback 字体**，只能把字做进字体文件里。

---

## 许可

脚本代码：**MIT**（见 `LICENSE`）。依赖 [fontTools](https://github.com/fonttools/fonttools)（MIT）。

仓库内**不包含任何字体文件**。你生成的字体受原字体许可约束，请自行确认。

## 致谢

- [fontTools](https://github.com/fonttools/fonttools) — 底层全靠它
- [Noto Sans SC](https://github.com/notofonts/noto-cjk) — 最常用的补字源（SIL OFL 1.1）
