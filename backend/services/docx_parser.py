"""
简历 DOCX 文件解析服务
"""
import re
from docx import Document
from lxml import etree


def parse_docx(file_path: str) -> dict:
    """解析 DOCX 简历文件，返回结构化数据"""
    doc = Document(file_path)

    # 用 XML 级别提取所有文本，确保不漏掉表格内容
    nsmap = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    body = doc.element.body

    section_texts = []
    current_section = []
    paragraphs_data = []

    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "p":
            # 段落
            texts = child.findall(".//w:t", nsmap)
            text = "".join(t.text or "" for t in texts)
            if text.strip():
                current_section.append(text.strip())
                paragraphs_data.append({
                    "text": text.strip(),
                    "style": "Normal",
                })

        elif tag == "tbl":
            # 表格 - 提取所有文本
            rows = child.findall(".//w:tr", nsmap)
            table_texts = []
            for row in rows:
                cells = row.findall(".//w:tc", nsmap)
                row_texts = []
                for cell in cells:
                    # 提取每个段落的文本
                    cell_paras = cell.findall(".//w:p", nsmap)
                    cell_para_texts = []
                    for cp in cell_paras:
                        cp_texts = cp.findall(".//w:t", nsmap)
                        cp_text = "".join(t.text or "" for t in cp_texts).strip()
                        if cp_text:
                            cell_para_texts.append(cp_text)
                    cell_text = "\n".join(cell_para_texts)
                    if cell_text:
                        row_texts.append(cell_text)
                if row_texts:
                    table_texts.append(" | ".join(row_texts))
                    # 单个单元格的文本也加入
                    for rt in row_texts:
                        if rt not in current_section:
                            current_section.append(rt)
            if table_texts:
                section_texts.append("\n".join(table_texts))

        elif tag == "sectPr":
            # 分节符
            if current_section:
                section_texts.append("\n".join(current_section))
                current_section = []

    # 最后一部分
    if current_section:
        section_texts.append("\n".join(current_section))

    full_text = "\n\n".join(section_texts)

    # 提取基本信息
    info = _extract_basic_info(full_text)

    return {
        "full_text": full_text,
        "paragraphs": paragraphs_data,
        "info": info,
    }


def parse_jd_txt(file_path: str) -> str:
    """解析岗位 JD 文本文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def parse_jd_text(text: str) -> str:
    """直接解析 JD 文本内容"""
    return text.strip()


def _extract_basic_info(full_text: str) -> dict:
    """提取姓名、联系方式等基本信息"""
    lines = full_text.split("\n")

    name = ""
    phone = ""
    email = ""

    # 第一行通常包含姓名
    for line in lines[:5]:
        cleaned = line.strip()
        if not cleaned:
            continue
        if "姓名" in cleaned:
            name = cleaned.replace("姓名：", "").replace("姓名:", "").replace("姓名", "").strip()
            break
        elif len(cleaned) < 15 and not any(c in cleaned for c in ["【", "】", "@", "|"]):
            name = cleaned
            break

    # 提取联系方式
    phone_match = re.search(r"(\+?\d{10,13})", full_text)
    if phone_match:
        phone = phone_match.group(1)

    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", full_text)
    if email_match:
        email = email_match.group(0)

    return {
        "name": name,
        "phone": phone,
        "email": email,
        "raw_text": full_text,
    }