#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aping Workbench daily content generator.
Module 3 (news-analysis): fetch domestic headlines, analyze impact from 4 perspectives.
Module 2 (ai-briefing): fetch global AI news, translate to Chinese, build Markdown briefing + SVG infographic.
Output written to /workspace/data/*.json.
"""
import urllib.request, json, datetime, re, os, time, html as ihtml

try:
    from deep_translator import GoogleTranslator
    _TRANSLATOR = GoogleTranslator(source='auto', target='zh-CN')
except Exception:
    _TRANSLATOR = None

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


def translate_texts(texts):
    if not _TRANSLATOR or not texts:
        return texts
    try:
        out = []
        for i in range(0, len(texts), 5):
            batch = texts[i:i + 5]
            out.extend(_TRANSLATOR.translate_batch(batch))
            time.sleep(0.3)
        return out
    except Exception as e:
        print("[translate warn]", e)
        return texts



# ---------- 模块3：央视《新闻联播》每日深度分析 ----------
XWLB_HOME = "https://tv.cctv.com/lm/xwlb/"
FALLBACK_SRC = "https://www.chinanews.com.cn/rss/scroll-news.xml"

DOMAIN_RULES = [
    ("外交国际", ["习近平","总统","总理","外交","国际","外长","会谈","通话","双边","峰会","一带一路","联合国","访问","金正恩","伊朗","美国","俄罗斯","乌克兰","沙特","胡塞","以军","黎巴嫩","北太平洋","公海","志愿军","巴西","两国"]),
    ("经济产业", ["工业","利润","外贸","经济","增长","消费","市场","投资","产业","企业","金融","税收","招商","进博会","吞吐量","特高压","装粮","粮仓","油价","营收","订单","发展","生产"]),
    ("科技创新", ["科技","创新","人工智能","芯片","航天","研发","数字","智能","卫星","量子","5G","新能源","半导体","空间采集","文物01星","技术","数据"]),
    ("政策法治", ["规划","法治","政策","条例","法律","会议","印发","转发","通知","决定","部署","治理","改革","制度","宣传","司法","网信","党中央","国务院"]),
    ("民生保障", ["民生","医疗","社保","养老","住房","就业","收入","低保","惠民","健康","安全","残疾人","服务","气象","红霞","应对","保障","幸福"]),
    ("教育人才", ["高校","大学","教育","人才","招生","科研","学科","培养","学校","学院","学术","职业"]),
    ("农业农村", ["农业","农村","农民","粮食","乡村振兴","春耕","丰收","养殖","种植","唐山","三农"]),
    ("生态环保", ["生态","环保","绿色","低碳","污染","减排","双碳","环境","自然遗产","世界自然","节能"]),
    ("文化体育", ["文化","体育","文物","旅游","非遗","文艺","侨批","博物馆","赛事"]),
]

def detect_domain(text):
    text = text or ""
    for dom, kws in DOMAIN_RULES:
        for k in kws:
            if k in text:
                return dom
    return "综合"

PERSPECTIVE_TEMPLATES = {
    "行政官员": {
        "外交国际": "从行政官员视角看，「{t}」属国家对外交往的重要议程。外交与外事条线需统一口径、做好风险研判与后续跟进，把高层共识转化为可落地的合作成果，服务国家总体外交与稳定发展大局。",
        "经济产业": "从行政官员视角看，「{t}」折射出经济运行的新信号。发改、工信、财政等部门应加强统筹与跨周期调节，打通政策传导堵点，把稳增长、稳预期、惠民生的举措精准送到企业与基层。",
        "科技创新": "从行政官员视角看，「{t}」指向关键领域的创新攻坚。科技与产业主管部门应完善组织机制与资源保障，推动产学研协同与“揭榜挂帅”，把创新资源集中投向国家战略急需方向。",
        "政策法治": "从行政官员视角看，「{t}」是政策部署落地的重要环节。相关职能部门须抓紧制定配套细则，明确责任分工、时间节点与督查机制，确保文件要求转化为可感可及的治理实效。",
        "民生保障": "从行政官员视角看，「{t}」直接关系群众切身利益。主管部门要吃透精神、细化举措、强化监督，防止政策“上下一般粗”，真正把惠民实事办到群众心坎上并接受实效检验。",
        "教育人才": "从行政官员视角看，「{t}」关乎教育供给与人才支撑。教育及人社部门应优化资源配置，引导高校学科与人才培养向国家急需领域集聚，强化产教融合与就业服务衔接。",
        "农业农村": "从行政官员视角看，「{t}」事关粮食安全和乡村全面振兴。农业农村及相关部门应压实责任、强化要素保障，统筹产业发展、基层治理与农民增收，夯实“三农”基本盘。",
        "生态环保": "从行政官员视角看，「{t}」体现绿色发展导向。生态环境与自然资源部门应强化刚性约束与空间管控，完善生态补偿与监管执法，推动降碳减污扩绿增长协同增效。",
        "文化体育": "从行政官员视角看，「{t}」承载文化自信与公共服务功能。文旅及宣传部门应做好保护传承与惠民供给，把文化资源转化为城乡品质提升与精神文明建设的有力抓手。",
        "综合": "从行政官员视角看，「{t}」要求相关职能部门强化统筹部署与闭环落实，明确时间表、路线图和责任主体，确保举措可操作、可督查、可评价。",
    },
    "高校": {
        "外交国际": "从高校视角看，「{t}」蕴含国际交流与学术合作的新机遇。高校可借此拓展联合研究、留学生交换与智库对话，将国家外交议程转化为人才培养与国际传播的教学资源。",
        "经济产业": "从高校视角看，「{t}」为经济学、管理学等学科提供了鲜活案例。高校可加强产业经济与区域发展研究，调整专业与课程供给，向产业一线输送适配的复合型人才。",
        "科技创新": "从高校视角看，「{t}」是科研攻关与平台建设的风向标。高校应围绕关键领域布局重点实验室与交叉学科，深化产学研合作，把论文写在产业链与国之重器上。",
        "政策法治": "从高校视角看，「{t}」关乎法治人才培养与智库供给。高校法学院系可加强相关领域教学科研，参与普法宣传与政策评估，为法治建设提供智力支持。",
        "民生保障": "从高校视角看，「{t}」提示高校应发挥社会服务职能。可依托医学、公共卫生、社会工作等学科参与基层治理与民生保障，把研究成果转化为惠民服务。",
        "教育人才": "从高校视角看，「{t}」直接影响招生、培养与就业导向。高校应前瞻调整学科专业结构，强化实践能力与产教融合，提升人才供给与产业需求的匹配度。",
        "农业农村": "从高校视角看，「{t}」为涉农学科提供广阔舞台。高校可加强农业科技创新与乡村规划研究，通过科技小院、定点帮扶等方式把成果送到田间地头。",
        "生态环保": "从高校视角看，「{t}」凸显生态文明教育的现实素材。高校可增设绿色技术与环境学科方向，开展生态科普与碳中和技术攻关，培养绿色低碳专业人才。",
        "文化体育": "从高校视角看，「{t}」是人文教育与文化传承的优质内容。高校可结合文史、艺术、文博等学科开展研究与传播，增强青年学生的文化认同与审美素养。",
        "综合": "从高校视角看，「{t}」为学校调整科研重点与人才培养方向提供了现实坐标。建议高校前瞻布局相关学科，强化应用导向与产学研协同。",
    },
    "商人公司": {
        "外交国际": "从商人/公司视角看，「{t}」往往伴随外贸与跨境合作机遇。相关企业应关注政策红利与市场准入变化，评估供应链与汇率风险，稳健拓展国际业务布局。",
        "经济产业": "从商人/公司视角看，「{t}」释放了明确的市场信号。企业需研判对需求、成本与合规的影响，把握其中扩产、升级或出海的业务机会，同时防范周期波动风险。",
        "科技创新": "从商人/公司视角看，「{t}」意味着新的技术赛道与采购需求。科技企业应评估研发投入与商业化节奏，关注国产替代、专精特新与首台套等政策窗口。",
        "政策法治": "从商人/公司视角看，「{t}」带来合规要求与政策机遇并存的局面。企业应及时对标新规，完善内控与合规体系，把政策红利转化为可持续的竞争优势。",
        "民生保障": "从商人/公司视角看，「{t}」打开民生消费与服务的市场空间。医疗、养老、消费等领域企业可围绕真实需求优化供给，在惠民中实现稳健经营。",
        "教育人才": "从商人/公司视角看，「{t}」凸显人才供需的结构性变化。企业应提前布局校招与在职培训，深化与高校订单式、项目制合作，缓解关键岗位用人压力。",
        "农业农村": "从商人/公司视角看，「{t}」指向乡村消费与农业产业链机会。涉农及食品企业可延伸加工、冷链与品牌链条，以订单农业带动农户共同增收。",
        "生态环保": "从商人/公司视角看，「{t}」既是合规压力也是绿色商机。高耗能行业须加快节能改造，新能源与环保企业则迎来设备更新与碳市场扩容的窗口。",
        "文化体育": "从商人/公司视角看，「{t}」带动文旅、内容与消费热度。相关企业可围绕文化IP、赛事与研学开发产品，把握体验经济与国潮消费的增长曲线。",
        "综合": "从商人/公司视角看，「{t}」提示企业应密切关注政策与市场环境变化，评估对订单、成本与合规的影响，在把握机会的同时管好风险。",
    },
    "行业协会": {
        "外交国际": "从行业协会视角看，「{t}」关乎行业出海的外部环境。协会可搭建国际合作与合规服务平台，组织企业对接海外渠道，统一应对贸易壁垒与标准差异。",
        "经济产业": "从行业协会视角看，「{t}」需要协会发挥桥梁与自律作用。可牵头研判行业走势、制定团体标准、引导有序竞争，并把企业诉求及时反馈给主管部门。",
        "科技创新": "从行业协会视角看，「{t}」是推进行业技术协同的契机。协会可组织联合攻关、成果对接与人才培训，促进创新链与产业链在会员单位间高效贯通。",
        "政策法治": "从行业协会视角看，「{t}」要求协会做好政策宣贯与自律规范。应引导会员单位对标新规、自查自纠，以团体标准与信用建设促进行业健康发展。",
        "民生保障": "从行业协会视角看，「{t}」强调服务的公益属性。协会可动员会员单位提升供给质量、规范服务流程，把惠民要求落到行业一线与消费终端。",
        "教育人才": "从行业协会视角看，「{t}」关联人才标准与职业资格。协会可完善行业人才评价与培训体系，推动校企共建，缓解结构性用工矛盾。",
        "农业农村": "从行业协会视角看，「{t}」利于协会联农带农、规范产销。可推广统一标准与品牌，组织产销对接，帮助会员单位与小农户共享产业链收益。",
        "生态环保": "从行业协会视角看，「{t}」推动行业绿色转型。协会可制定节能降碳团体标准、推广最佳实践，协调会员单位共建共享环保设施与碳资产。",
        "文化体育": "从行业协会视角看，「{t}」有助于规范文化与体育市场秩序。协会可强化版权保护、诚信经营与内容导向，引导会员单位创作更多优质文化产品。",
        "综合": "从行业协会视角看，「{t}」需要协会发挥协调与自律功能，推动标准共建、信息共享与政企沟通，引导会员单位在规范中协同发展。",
    },
}

def analyze_item(title):
    dom = detect_domain(title)
    out = {}
    for p, t in PERSPECTIVE_TEMPLATES.items():
        out[p] = t.get(dom, t["综合"]).replace("{t}", title)
    return out

def fetch_xwlb_items():
    """抓取央视《新闻联播》当日「本期节目主要内容」，返回 (date_iso, broadcast, items)。"""
    try:
        raw = fetch(XWLB_HOME)
    except Exception:
        return None
    m = re.search(r'href="([^"]*VIDE[^"]*\.shtml)"', raw)
    if not m:
        return None
    ep = m.group(1)
    if ep.startswith("//"):
        ep = "https:" + ep
    try:
        eh = fetch(ep)
    except Exception:
        return None
    dm = re.search(r'新闻联播[》]?\s*(\d{8})', eh)
    broadcast = dm.group(1) if dm else ""
    date_iso = (f"{broadcast[:4]}-{broadcast[4:6]}-{broadcast[6:8]}"
                if len(broadcast) == 8 else datetime.date.today().isoformat())
    mb = re.search(r'本期节目主要内容[:：](.*?)<', eh, re.S)
    block = mb.group(1) if mb else ""
    block = re.sub(r'<[^>]+>', ' ', block)
    block = re.sub(r'\s+', ' ', block)
    block = re.sub(r'（《新闻联播》.*$', '', block)
    segs = [s.strip() for s in block.split('；') if s.strip()]
    items = []
    for s in segs:
        mm = re.match(r'^(\d+)\.\s*(.*)$', s)
        if not mm:
            continue
        num = int(mm.group(1))
        content = mm.group(2).strip()
        subs = re.findall(r'（(\d+)）([^（）]+)', content)
        if subs and ('快讯' in content or len(subs) >= 2):
            cat = content.split('（')[0].strip().rstrip('：:')
            for _, st in subs:
                st = st.strip()
                if st:
                    items.append((num, cat + '：' + st))
        else:
            items.append((num, content))
    return date_iso, broadcast, items[:24]

def gen_news_analysis():
    res = fetch_xwlb_items()
    if res and res[2]:
        date_iso, broadcast, items = res
        source = "央视网《新闻联播》"
        note = "本模块每日 07:00 自动抓取央视《新闻联播》当日「本期节目主要内容」，对每条内容分别从 行政官员 / 高校 / 商人公司 / 行业协会 四个视角进行解读。"
    else:
        feeds = parse_feed(FALLBACK_SRC)
        items = [(i + 1, it["title"]) for i, it in enumerate(feeds[:12])]
        date_iso = datetime.date.today().isoformat()
        broadcast = ""
        source = "国内主流媒体要闻（央视源暂不可用，已用同源替代）"
        note = "央视《新闻联播》源本次抓取失败，已以国内主流媒体一手要闻作同源替代，四维解读逻辑一致。"
    analyzed = [{"no": n, "title": t, "analysis": analyze_item(t)} for n, t in items]
    domains = {}
    for n, t in items:
        d = detect_domain(t)
        domains[d] = domains.get(d, 0) + 1
    dom_str = "、".join(f"{k}（{v}）" for k, v in domains.items())
    top = "；".join(t for _, t in items[:4])
    summary = (f"本期《新闻联播》（{broadcast or date_iso}）共播报 {len(items)} 条主要内容，"
               f"涉及{dom_str}等领域。重点包括：{top} 等。")
    data = {
        "date": date_iso,
        "broadcast": broadcast,
        "source": source,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note": note,
        "total": len(items),
        "summary": summary,
        "items": analyzed,
        "raw_items": [t for _, t in items],
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
    p.append(f'<rect width="{W}" height="{H}" fill="#0b0f19"/>')
    p.append(f'<rect x="0" y="0" width="{W}" height="130" fill="#ff2d92"/>')
    p.append(f'<text x="{pad}" y="50" fill="#ffffff" font-size="30" font-weight="700">AI 动态每日简报</text>')
    p.append(f'<text x="{pad}" y="84" fill="#fce7f3" font-size="16">生成日期 {esc(date)} ｜ 来源 The Verge / TechCrunch（已译）</text>')
    cx = pad
    for c, n in cat_counts.items():
        if not n:
            continue
        label = f"{c} {n}"
        w = 24 + len(label) * 15
        p.append(f'<rect x="{cx}" y="100" width="{w}" height="22" rx="11" fill="#1e103c"/>')
        p.append(f'<text x="{cx+12}" y="116" fill="#fbcfe8" font-size="13">{esc(label)}</text>')
        cx += w + 10
    y = 158
    for idx, it in enumerate(items):
        title = it.get("title_zh") or it["title"]
        if len(title) > 34:
            title = title[:33] + "…"
        p.append(f'<rect x="{pad}" y="{y}" width="{W-2*pad}" height="{row_h-12}" rx="12" fill="#1e103c" stroke="#ff2d92"/>')
        p.append(f'<text x="{pad+18}" y="{y+36}" fill="#f9a8d4" font-size="20" font-weight="700">{idx+1}</text>')
        p.append(f'<text x="{pad+52}" y="{y+36}" fill="#ffffff" font-size="17">{esc(title)}</text>')
        p.append(f'<text x="{pad+52}" y="{y+62}" fill="#e9d5ff" font-size="13">AI 动态 ｜ 点击查看原文</text>')
        y += row_h
    p.append(f'<text x="{pad}" y="{H-16}" fill="#a78bfa" font-size="12">阿萍的工作台 ｜ 每日 09:00 自动生成</text>')
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

    # translate titles and summaries to Chinese
    titles_zh = translate_texts([i["title"] for i in items])
    descs_zh = translate_texts([i["desc"] for i in items])
    for it, tz, dz in zip(items, titles_zh, descs_zh):
        it["title_zh"] = tz
        it["desc_zh"] = dz

    today = datetime.date.today()
    cats = {"研究/模型": [], "产品/应用": [], "政策/行业": [], "其他": []}
    for i in items:
        cats[categorize(i["title"])].append(i)
    md = []
    md.append("# AI 动态每日简报\n")
    md.append(f"> 生成日期：**{today.isoformat()}** ｜ 来源：The Verge AI、TechCrunch AI（标题/摘要已译为中文，链接指向英文原文）\n")
    md.append("> 每日 09:00 自动抓取全球 AI 领域最新动态，整理为简报。\n")
    for c in ["研究/模型", "产品/应用", "政策/行业", "其他"]:
        its = cats[c][:5]
        if not its:
            continue
        md.append(f"\n## {c}（{len(its)} 条）\n")
        for i in its:
            note = (i.get("desc_zh") or i["desc"])[:90] + "…" if (i.get("desc_zh") or i["desc"]) else "（暂无摘要）"
            title = i.get("title_zh") or i["title"]
            md.append(f"- **{title}**  \n  {note}  \n  🔗 {i['link']}\n")
    cat_counts = {c: len(v) for c, v in cats.items() if v}
    svg = infographic_svg(items[:6], today.isoformat(), cat_counts)
    data = {
        "date": today.isoformat(),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "briefing_md": "\n".join(md),
        "infographic_svg": svg,
        "items": [{"title": i["title"], "title_zh": i.get("title_zh", ""), "link": i["link"]} for i in items[:12]],
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
