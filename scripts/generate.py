#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aping Workbench daily content generator.
Module 3 (news-analysis): fetch domestic headlines, analyze impact from 4 perspectives.
Module 2 (ai-briefing): fetch global AI news, build Markdown briefing + SVG infographic.
Output written to /workspace/data/*.json.
"""
import urllib.request, json, datetime, re, os, html as ihtml

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
WS = "/workspace"
DATA = os.path.join(WS, "data")

NEWS3_SRC = "https://www.chinanews.com.cn/rss/scroll-news.xml"
AI_SRCS = [
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
]

PERSPECTIVES = {
    "行政官员": ["政策", "政府", "国务院", "部长", "部署", "监管", "执法", "通知", "发改委", "工信部",
              "发文", "督查", "落地", "统筹", "民生", "行政", "中央", "省市", "措施", "改革", "会议"],
    "高校": ["高校", "大学", "教育", "科研", "学生", "招生", "学术", "实验室", "院所", "培养",
            "课题", "教研", "院系", "学位", "校园", "学者"],
    "商人公司": ["企业", "公司", "市场", "上市", "融资", "营收", "股价", "产品", "消费", "客户",
              "投资", "并购", "创业", "利润", "品牌", "厂商", "供应", "订单", "业务"],
    "协会": ["协会", "行业", "标准", "规范", "自律", "联盟", "商会", "行会", "倡议", "团体",
            "学会", "公会"],
}


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", "replace")


def un_cdata(s):
    return re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.S)


def clean(s):
    if not s:
        return ""
    s = un_cdata(s)
    s = re.sub(r"<[^>]+>", "", s)
    s = ihtml.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_feed(url):
    try:
        raw = fetch(url)
    except Exception:
        return []
    items = []
    for m in re.finditer(r"<item[^>]*>(.*?)</item>", raw, re.S):
        it = m.group(1)
        t = re.search(r"<title[^>]*>(.*?)</title>", it, re.S)
        l = re.search(r"<link[^>]*>(.*?)</link>", it, re.S)
        d = re.search(r"<description[^>]*>(.*?)</description>", it, re.S)
        p = re.search(r"<pubDate[^>]*>(.*?)</pubDate>", it, re.S)
        title = clean(t.group(1)) if t else ""
        if title:
            items.append({"title": title, "link": clean(l.group(1)) if l else "",
                          "desc": clean(d.group(1)) if d else "", "pub": clean(p.group(1)) if p else ""})
    for m in re.finditer(r"<entry[^>]*>(.*?)</entry>", raw, re.S):
        it = m.group(1)
        t = re.search(r"<title[^>]*>(.*?)</title>", it, re.S)
        l = re.search(r'<link[^>]*href="([^"]+)"', it)
        d = re.search(r"<summary[^>]*>(.*?)</summary>", it, re.S)
        title = clean(t.group(1)) if t else ""
        if title:
            items.append({"title": title,
                          "link": l.group(1) if l else "",
                          "desc": clean(d.group(1)) if d else "", "pub": ""})
    return items[:30]


def impact_text(persp, area):
    if persp == "行政官员":
        return f"对行政体系而言，该动向要求相关职能部门在「{area}」上加强统筹与落地执行，关注政策的可操作性与民生实效，做好跨部门协同与进度督导。"
    if persp == "高校":
        return f"对高校而言，「{area}」将影响学科布局、招生培养与产学研合作方向，建议提前调整科研重点与人才储备方案，强化应用导向。"
    if persp == "商人公司":
        return f"对企业而言，这条信息意味着在「{area}」领域出现新的市场变量，需评估对需求、成本与合规的影响，把握其中的业务机会或对冲风险。"
    if persp == "协会":
        return f"对行业协会而言，可借机推动「{area}」领域的标准制定与自律规范，引导会员单位有序应对，发挥补位与协调作用。"
    return f"在「{area}」层面需予以关注。"


def gen_news_analysis():
    items = parse_feed(NEWS3_SRC)
    today = datetime.date.today()
    buckets = {k: [] for k in PERSPECTIVES}
    for it in items:
        text = it["title"] + " " + it["desc"]
        for persp, kws in PERSPECTIVES.items():
            hit = [k for k in kws if k in text]
            if hit:
                area = hit[0]
                buckets[persp].append({"title": it["title"], "link": it["link"], "area": area,
                                        "impact": impact_text(persp, area)})
    analysis = {}
    for persp in PERSPECTIVES:
        analysis[persp] = buckets[persp][:5]
    data = {
        "date": today.isoformat(),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "中国新闻网·滚动新闻（国内一手要闻）",
        "note": "新闻联播暂无公开 RSS，本模块以国内主流媒体一手要闻为同源替代，按 行政 / 高校 / 商业 / 行业 四维系统解读其影响。",
        "total": len(items),
        "analysis": analysis,
        "raw_items": [{"title": i["title"], "link": i["link"]} for i in items[:15]],
    }
    return data


def categorize(title):
    if re.search(r"model|模型|gpt|claude|gemini|llama|开源|论文|study|research|benchmark|训练|大模型|基座", title, re.I):
        return "研究/模型"
    if re.search(r"policy|regulat|政策|监管|法案|法规|中美|出口|反垄断|合规|政府|禁令", title, re.I):
        return "政策/行业"
    if re.search(r"app|product|产品|发布|launch|工具|平台|手机|芯片|chip|gpu|上线|融资|收购|应用|助手", title, re.I):
        return "产品/应用"
    return "其他"


def infographic_svg(items, date, cat_counts):
    W, pad = 820, 28
    rows = min(len(items), 6)
    row_h = 86
    H = 210 + rows * row_h
    esc = ihtml.escape
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'font-family="-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">']
    p.append(f'<rect width="{W}" height="{H}" fill="#0f2417"/>')
    p.append(f'<rect x="0" y="0" width="{W}" height="130" fill="#2f5e2d"/>')
    p.append(f'<text x="{pad}" y="50" fill="#ffffff" font-size="30" font-weight="700">AI 动态每日简报</text>')
    p.append(f'<text x="{pad}" y="84" fill="#cfe8d0" font-size="16">生成日期 {esc(date)} ｜ 来源 The Verge / TechCrunch</text>')
    cx = pad
    for c, n in cat_counts.items():
        if not n:
            continue
        label = f"{c} {n}"
        w = 24 + len(label) * 15
        p.append(f'<rect x="{cx}" y="100" width="{w}" height="22" rx="11" fill="#1c3a26"/>')
        p.append(f'<text x="{cx+12}" y="116" fill="#a9d8b4" font-size="13">{esc(label)}</text>')
        cx += w + 10
    y = 158
    for idx, it in enumerate(items):
        title = it["title"]
        if len(title) > 33:
            title = title[:32] + "…"
        p.append(f'<rect x="{pad}" y="{y}" width="{W-2*pad}" height="{row_h-12}" rx="12" fill="#15301f" stroke="#2f5e2d"/>')
        p.append(f'<text x="{pad+18}" y="{y+36}" fill="#7CFC9A" font-size="20" font-weight="700">{idx+1}</text>')
        p.append(f'<text x="{pad+52}" y="{y+36}" fill="#ffffff" font-size="17">{esc(title)}</text>')
        p.append(f'<text x="{pad+52}" y="{y+62}" fill="#9fb8a6" font-size="13">AI 动态 ｜ 点击查看原文</text>')
        y += row_h
    p.append(f'<text x="{pad}" y="{H-16}" fill="#7a947f" font-size="12">阿萍的工作台 ｜ 每日 09:00 自动生成</text>')
    p.append('</svg>')
    return "".join(p)


def gen_ai_briefing():
    raw = []
    for src in AI_SRCS:
        raw += parse_feed(src)
    seen, items = set(), []
    for i in raw:
        if i["title"] not in seen:
            seen.add(i["title"])
            items.append(i)
    items = items[:12]
    today = datetime.date.today()
    cats = {"研究/模型": [], "产品/应用": [], "政策/行业": [], "其他": []}
    for i in items:
        cats[categorize(i["title"])].append(i)
    md = []
    md.append("# AI 动态每日简报\n")
    md.append(f"> 生成日期：**{today.isoformat()}** ｜ 来源：The Verge AI、TechCrunch AI\n")
    md.append("> 每日 09:00 自动抓取全球 AI 领域最新动态，整理为简报。\n")
    for c in ["研究/模型", "产品/应用", "政策/行业", "其他"]:
        its = cats[c][:5]
        if not its:
            continue
        md.append(f"\n## {c}（{len(its)} 条）\n")
        for i in its:
            note = (i["desc"][:90] + "…") if i["desc"] else "（暂无摘要）"
            md.append(f"- **{i['title']}**  \n  {note}  \n  🔗 {i['link']}\n")
    cat_counts = {c: len(v) for c, v in cats.items() if v}
    svg = infographic_svg(items[:6], today.isoformat(), cat_counts)
    data = {
        "date": today.isoformat(),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "briefing_md": "\n".join(md),
        "infographic_svg": svg,
        "items": [{"title": i["title"], "link": i["link"]} for i in items[:12]],
    }
    return data


def main():
    na = gen_news_analysis()
    with open(os.path.join(DATA, "news-analysis.json"), "w", encoding="utf-8") as f:
        json.dump(na, f, ensure_ascii=False, indent=2)
    ab = gen_ai_briefing()
    with open(os.path.join(DATA, "ai-briefing.json"), "w", encoding="utf-8") as f:
        json.dump(ab, f, ensure_ascii=False, indent=2)
    print("OK news-analysis:", na["date"], "items", na["total"])
    print("OK ai-briefing:", ab["date"], "items", len(ab["items"]))


if __name__ == "__main__":
    main()
