#!/usr/bin/env python3
"""
简历格式化脚本
将 bbb.docx 按照标准求职简历排版要求重新排版，输出 bbb_formatted.docx

标准简历排版规范：
- 页面: A4 纸, 上下边距 2.0cm, 左右边距 2.2cm
- 姓名: 黑体, 22pt, 居中, 加粗
- 应聘职位: 宋体, 12pt, 居中
- 联系信息: 宋体, 10.5pt, 居中, 一行展示
- 一级标题 (如"工作经验"): 黑体, 14pt, 加粗, 带底部边框线
- 二级标题 (如公司/项目名): 宋体, 12pt, 加粗
- 正文内容: 宋体, 11pt, 行距 1.15 倍
- 英文/数字: Calibri
"""

import re
import copy
from docx import Document
from docx.shared import Pt, Cm, Emu, RGBColor, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml


# ── 配置 ──────────────────────────────────────────────
INPUT_FILE = "bbb.docx"
OUTPUT_FILE = "bbb_formatted.docx"

# 页面
PAGE_TOP_MARGIN = Cm(2.0)
PAGE_BOTTOM_MARGIN = Cm(2.0)
PAGE_LEFT_MARGIN = Cm(2.2)
PAGE_RIGHT_MARGIN = Cm(2.2)

# 字体 — 匹配原始简历风格
CN_FONT_TITLE = "宋体"          # 一级标题、小标题
CN_FONT_BODY = "KaiTi"          # 正文楷体
EN_FONT = "Calibri"             # 英文/数字

# 字号
NAME_SIZE = Pt(14)              # 姓名（原始为14pt宋体）
POSITION_SIZE = Pt(14)          # 应聘职位
CONTACT_SIZE = Pt(12)           # 联系方式
SECTION_HEADING_SIZE = Pt(10)   # 一级标题（如"一、工作经验："）
SUB_HEADING_SIZE = Pt(12)       # 二级标题（时段/项目名/技术栈）
LABEL_SIZE = Pt(10)             # 小标签（"项目描述：""工作内容与成果："）
BODY_SIZE = Pt(12)              # 正文楷体
TECH_STACK_SIZE = Pt(10)        # 技术栈行

# 行距
LINE_SPACING = 1.35             # 接近原文的行距

# 颜色
COLOR_BLACK = RGBColor(0x00, 0x00, 0x00)
COLOR_HEADING = RGBColor(0x00, 0x00, 0x00)


# ── 辅助函数 ──────────────────────────────────────────

def set_run_font(run, cn_font, en_font, size, bold=False, italic=False, color=COLOR_BLACK):
    """统一设置 run 的中英文字体、字号等。"""
    run.font.size = size
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = en_font
    # 设置中文字体（东亚字体）
    r = run._element
    rPr = r.find(qn("w:rPr"))
    if rPr is None:
        rPr = parse_xml(f'<w:rPr {nsdecls("w")}></w:rPr>')
        r.insert(0, rPr)
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = parse_xml(f'<w:rFonts {nsdecls("w")}/>')
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:eastAsia"), cn_font)
    rFonts.set(qn("w:ascii"), en_font)
    rFonts.set(qn("w:hAnsi"), en_font)


def set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.LEFT,
                         space_before=Pt(0), space_after=Pt(0),
                         line_spacing=LINE_SPACING, first_line_indent=None):
    """统一设置段落格式。"""
    fmt = paragraph.paragraph_format
    fmt.alignment = alignment
    fmt.space_before = space_before
    fmt.space_after = space_after
    fmt.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    fmt.line_spacing = line_spacing
    if first_line_indent is not None:
        fmt.first_line_indent = first_line_indent
    else:
        fmt.first_line_indent = Pt(0)
    # 清除段前分页
    fmt.page_break_before = False
    fmt.keep_with_next = False
    fmt.widow_control = True


def add_text_run(paragraph, text, cn_font, en_font, size,
                 bold=False, italic=False, color=COLOR_BLACK):
    """添加一个格式化的 run。"""
    run = paragraph.add_run(text)
    set_run_font(run, cn_font, en_font, size, bold, italic, color)
    return run


def add_section_heading(doc, title):
    """添加一级标题段落（如 "一、工作经验："），宋体加粗，无装饰线。"""
    p = doc.add_paragraph()
    set_paragraph_format(p, WD_ALIGN_PARAGRAPH.LEFT,
                         space_before=Pt(12), space_after=Pt(4))
    add_text_run(p, title, CN_FONT_TITLE, EN_FONT, SECTION_HEADING_SIZE,
                 bold=False, color=COLOR_BLACK)


def add_sub_heading(doc, text, bold=True, size=SUB_HEADING_SIZE):
    """添加二级标题（如时间段、职位、项目名）。"""
    p = doc.add_paragraph()
    set_paragraph_format(p, WD_ALIGN_PARAGRAPH.LEFT,
                         space_before=Pt(6), space_after=Pt(2))
    add_text_run(p, text, CN_FONT_BODY, EN_FONT, size, bold=bold)
    return p


def add_body_text(doc, text, indent=False, left_indent=None,
                  space_before=Pt(2), space_after=Pt(2)):
    """添加楷体正文段落。"""
    p = doc.add_paragraph()
    first_indent = Cm(0.74) if indent else Pt(0)
    set_paragraph_format(p, WD_ALIGN_PARAGRAPH.LEFT,
                         space_before=space_before, space_after=space_after,
                         first_line_indent=first_indent)
    if left_indent is not None:
        p.paragraph_format.left_indent = left_indent
    add_text_run(p, text, CN_FONT_BODY, EN_FONT, BODY_SIZE)
    return p


def add_tech_stack_line(doc, text):
    """添加技术栈行（Calibri 加粗）。"""
    p = doc.add_paragraph()
    set_paragraph_format(p, WD_ALIGN_PARAGRAPH.LEFT,
                         space_before=Pt(2), space_after=Pt(4))
    add_text_run(p, text, CN_FONT_TITLE, EN_FONT, TECH_STACK_SIZE, bold=True,
                 color=COLOR_BLACK)
    return p


def add_label_text(doc, text, space_before=Pt(10), space_after=Pt(4)):
    """添加宋体加粗小标签（如 '项目描述：' '工作内容与成果：'）。"""
    p = doc.add_paragraph()
    set_paragraph_format(p, WD_ALIGN_PARAGRAPH.LEFT,
                         space_before=space_before, space_after=space_after)
    add_text_run(p, text, CN_FONT_TITLE, EN_FONT, LABEL_SIZE,
                 bold=False, color=COLOR_BLACK)
    return p


# ── 内容提取 ──────────────────────────────────────────

def extract_content(doc):
    """从原始 docx 提取结构化内容。"""
    paragraphs = doc.paragraphs
    texts = [p.text.strip() for p in paragraphs]

    content = {
        "position": "",    # 应聘职位
        "name": "",
        "gender_age": "",
        "contact": "",
        "work_experience": [],   # list of {period, title, tech, duties:[]}
        "skills": [],            # list of str
        "projects": [],          # list of {name_tech, desc, duties:[]}
        "self_eval": "",
    }

    # --- 应聘职位 ---
    for t in texts:
        if t.startswith("应聘"):
            content["position"] = t.replace("应聘：", "").replace("应聘:", "").strip()
            break

    # --- 姓名 ---
    content["name"] = texts[1] if len(texts) > 1 else ""

    # --- 性别年龄 ---
    for t in texts:
        if "性别" in t and "年龄" in t:
            content["gender_age"] = t
            break

    # --- 联系方式 ---
    for t in texts:
        if "电话" in t and "邮箱" in t:
            content["contact"] = t
            break

    # --- 定位各节的起止索引 ---
    section_starts = {}
    section_order = []
    for i, t in enumerate(texts):
        if t.startswith("一、"):
            section_starts["work"] = i
            section_order.append("work")
        elif t.startswith("二、"):
            section_starts["skill"] = i
            section_order.append("skill")
        elif t.startswith("三、"):
            section_starts["project"] = i
            section_order.append("project")
        elif t.startswith("四、"):
            section_starts["eval"] = i
            section_order.append("eval")

    def section_range(key):
        idx = section_order.index(key)
        start = section_starts[key]
        end = section_starts[section_order[idx + 1]] if idx + 1 < len(section_order) else len(texts)
        return start, end

    # --- 工作经验 ---
    if "work" in section_starts:
        s, e = section_range("work")
        _parse_work_experience(texts[s + 1:e], content)

    # --- 专业技能 ---
    if "skill" in section_starts:
        s, e = section_range("skill")
        for t in texts[s + 1:e]:
            t = t.strip()
            if t:
                content["skills"].append(t)

    # --- 项目经验 ---
    if "project" in section_starts:
        s, e = section_range("project")
        _parse_projects(texts[s + 1:e], content)

    # --- 自我评价 ---
    if "eval" in section_starts:
        s, e = section_range("eval")
        eval_text = ""
        for t in texts[s + 1:e]:
            t = t.strip()
            if t:
                eval_text += t
        content["self_eval"] = eval_text

    return content


def _parse_work_experience(lines, content):
    """解析工作经验段落。"""
    current = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 时间段 (e.g. "2022.04-今" or "2019.06-2022.04")
        if re.match(r"^\d{4}\.\d{2}\s*[-–—]\s*(\d{4}\.\d{2}|今|至今)", line):
            if current:
                content["work_experience"].append(current)
            current = {"period": line, "title": "", "tech": "", "duties": []}
        elif current is not None:
            if not current["title"]:
                current["title"] = line
            elif not current["tech"] and any(kw in line for kw in ["Vue", "React", "Node", "Vite", "Pinia", "Vuex"]):
                current["tech"] = line
            else:
                # 职责条目
                current["duties"].append(line)
    if current:
        content["work_experience"].append(current)


def _parse_projects(lines, content):
    """解析项目经验段落。"""
    current = None
    in_desc = False
    in_duties = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 项目标题行：以数字+、开头，且包含技术栈关键词
        if re.match(r"^\d+[、.]", line) and "技术栈" in line:
            if current:
                content["projects"].append(current)
            current = {"name_tech": line, "desc": "", "duties": []}
            in_desc = False
            in_duties = False
            continue

        if current is None:
            continue

        if line.startswith("项目描述"):
            in_desc = True
            in_duties = False
            # 项目描述可能在同一行
            rest = line.replace("项目描述：", "").replace("项目描述:", "").strip()
            if rest:
                current["desc"] += rest
            continue

        if line.startswith("工作内容与成果"):
            in_desc = False
            in_duties = True
            continue

        if in_duties:
            current["duties"].append(line)
        elif in_desc:
            current["desc"] += line
        # 其它内容也归入描述
        elif not in_desc and not in_duties:
            current["desc"] += line

    if current:
        content["projects"].append(current)


# ── 合并断行的技能条目 ──────────────────────────────────

def merge_skill_items(skills):
    """
    将因 PDF 断行而拆开的技能条目重新合并。
    以数字+、或数字+. 开头的视为新条目，否则追加到上一条。
    """
    merged = []
    for s in skills:
        if re.match(r"^\d+[、.]", s):
            merged.append(s)
        elif merged:
            merged[-1] += s
        else:
            merged.append(s)
    return merged


def merge_duty_items(duties):
    """合并断行的工作职责条目。"""
    merged = []
    for d in duties:
        if re.match(r"^\d+[\.\、]", d):
            merged.append(d)
        elif merged:
            merged[-1] += d
        else:
            merged.append(d)
    return merged


# ── 构建新文档 ──────────────────────────────────────────

def build_resume(content):
    """根据提取的内容构建标准格式简历。"""
    doc = Document()

    # ── 页面设置 ──
    section = doc.sections[0]
    section.page_width = Cm(21.0)   # A4
    section.page_height = Cm(29.7)  # A4
    section.top_margin = PAGE_TOP_MARGIN
    section.bottom_margin = PAGE_BOTTOM_MARGIN
    section.left_margin = PAGE_LEFT_MARGIN
    section.right_margin = PAGE_RIGHT_MARGIN

    # ── 设置默认样式 ──
    style = doc.styles["Normal"]
    style.font.name = EN_FONT
    style.font.size = BODY_SIZE
    style.element.rPr.rFonts.set(qn("w:eastAsia"), CN_FONT_BODY)
    style.paragraph_format.space_before = Pt(0)
    style.paragraph_format.space_after = Pt(0)
    style.paragraph_format.line_spacing = LINE_SPACING

    # ============================================================
    # 1. 应聘职位（左对齐，宋体）
    # ============================================================
    p_pos = doc.add_paragraph()
    set_paragraph_format(p_pos, WD_ALIGN_PARAGRAPH.LEFT,
                         space_before=Pt(0), space_after=Pt(0))
    add_text_run(p_pos, f"应聘：", CN_FONT_TITLE, EN_FONT, POSITION_SIZE)
    add_text_run(p_pos, content["position"], CN_FONT_TITLE, EN_FONT,
                 POSITION_SIZE, bold=True)

    # ============================================================
    # 2. 姓名
    # ============================================================
    p_name = doc.add_paragraph()
    set_paragraph_format(p_name, WD_ALIGN_PARAGRAPH.LEFT,
                         space_before=Pt(8), space_after=Pt(2))
    add_text_run(p_name, content["name"], CN_FONT_BODY, EN_FONT, NAME_SIZE)

    # ============================================================
    # 3. 联系信息（楷体，分两行：性别年龄 / 电话邮箱）
    # ============================================================
    ga = content["gender_age"]
    if ga:
        p_ga = doc.add_paragraph()
        set_paragraph_format(p_ga, WD_ALIGN_PARAGRAPH.LEFT,
                             space_before=Pt(6), space_after=Pt(2))
        add_text_run(p_ga, ga, CN_FONT_BODY, EN_FONT, CONTACT_SIZE)

    ct = content["contact"]
    if ct:
        p_ct = doc.add_paragraph()
        set_paragraph_format(p_ct, WD_ALIGN_PARAGRAPH.LEFT,
                             space_before=Pt(2), space_after=Pt(6))
        add_text_run(p_ct, ct, CN_FONT_BODY, EN_FONT, CONTACT_SIZE)

    # ============================================================
    # 4. 工作经验
    # ============================================================
    if content["work_experience"]:
        add_section_heading(doc, "一、工作经验：")
        for exp in content["work_experience"]:
            # 时间段 + 职位（同一行，用 Tab 右对齐分隔）
            p_line = doc.add_paragraph()
            set_paragraph_format(p_line, WD_ALIGN_PARAGRAPH.LEFT,
                                 space_before=Pt(4), space_after=Pt(0))
            # 添加右对齐 tab stop
            tab_stops = p_line.paragraph_format.tab_stops
            # 页宽 21cm - 左右边距 2.2cm*2 = 16.6cm 可用宽度
            tab_stops.add_tab_stop(Cm(16.6), WD_TAB_ALIGNMENT.RIGHT)
            add_text_run(p_line, exp["period"], CN_FONT_BODY, EN_FONT, BODY_SIZE)
            add_text_run(p_line, "\t", CN_FONT_BODY, EN_FONT, BODY_SIZE)
            add_text_run(p_line, exp["title"], CN_FONT_BODY, EN_FONT, BODY_SIZE)

            # 技术栈（Calibri 加粗，缩进）
            if exp["tech"]:
                p_tech = doc.add_paragraph()
                set_paragraph_format(p_tech, WD_ALIGN_PARAGRAPH.LEFT,
                                     space_before=Pt(0), space_after=Pt(2))
                p_tech.paragraph_format.left_indent = Cm(0.5)
                add_text_run(p_tech, exp["tech"], CN_FONT_TITLE, EN_FONT,
                             TECH_STACK_SIZE, bold=True)

            # 工作职责（首行缩进）
            duties = merge_duty_items(exp["duties"])
            for duty in duties:
                add_body_text(doc, duty, indent=True,
                              space_before=Pt(1), space_after=Pt(1))

    # ============================================================
    # 5. 专业技能
    # ============================================================
    if content["skills"]:
        add_section_heading(doc, "二、专业技能：")
        merged_skills = merge_skill_items(content["skills"])
        for skill in merged_skills:
            add_body_text(doc, skill, indent=True,
                          space_before=Pt(3), space_after=Pt(3))

    # ============================================================
    # 6. 项目经验
    # ============================================================
    if content["projects"]:
        add_section_heading(doc, "三、项目经验：")
        for proj in content["projects"]:
            # 拆分项目名和技术栈
            name_tech = proj["name_tech"]
            tech_match = re.search(r"技术栈[：:](.+)", name_tech)
            proj_name_match = re.match(r"(\d+[、.].+?)技术栈", name_tech)
            proj_name = proj_name_match.group(1).strip() if proj_name_match else name_tech

            # 项目名（单独一行）
            p_proj = doc.add_paragraph()
            set_paragraph_format(p_proj, WD_ALIGN_PARAGRAPH.LEFT,
                                 space_before=Pt(8), space_after=Pt(2))
            add_text_run(p_proj, proj_name, CN_FONT_BODY, EN_FONT, BODY_SIZE)

            # 技术栈（单独一行，带缩进和 "技术栈：" 前缀）
            if tech_match:
                tech_text = tech_match.group(1).strip()
                p_tech = doc.add_paragraph()
                set_paragraph_format(p_tech, WD_ALIGN_PARAGRAPH.LEFT,
                                     space_before=Pt(0), space_after=Pt(2))
                p_tech.paragraph_format.left_indent = Cm(0.5)
                add_text_run(p_tech, f"技术栈：{tech_text}",
                             CN_FONT_BODY, EN_FONT, BODY_SIZE)

            # 项目描述：（宋体标签）
            if proj["desc"]:
                add_label_text(doc, "项目描述：",
                               space_before=Pt(6), space_after=Pt(2))
                # 描述正文（楷体，首行缩进）
                add_body_text(doc, proj["desc"], indent=True,
                              space_before=Pt(0), space_after=Pt(4))

            # 工作内容与成果：（宋体标签）
            duties = merge_duty_items(proj["duties"])
            if duties:
                add_label_text(doc, "工作内容与成果：",
                               space_before=Pt(6), space_after=Pt(2))
                for duty in duties:
                    # 编号条目用首行缩进
                    add_body_text(doc, duty, indent=True,
                                  space_before=Pt(2), space_after=Pt(2))

    # ============================================================
    # 7. 自我评价
    # ============================================================
    if content["self_eval"]:
        add_section_heading(doc, "四、自我评价：")
        add_body_text(doc, content["self_eval"], indent=True,
                      space_before=Pt(4), space_after=Pt(4))

    return doc


# ── 主入口 ──────────────────────────────────────────

def main():
    print(f"读取源文件：{INPUT_FILE}")
    src = Document(INPUT_FILE)

    print("提取简历内容...")
    content = extract_content(src)

    print(f"  姓名: {content['name']}")
    print(f"  应聘: {content['position']}")
    print(f"  工作经验: {len(content['work_experience'])} 段")
    print(f"  专业技能: {len(content['skills'])} 条")
    print(f"  项目经验: {len(content['projects'])} 个")

    print("构建标准格式简历...")
    doc = build_resume(content)

    doc.save(OUTPUT_FILE)
    print(f"\n✅ 格式化完成，已输出: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
