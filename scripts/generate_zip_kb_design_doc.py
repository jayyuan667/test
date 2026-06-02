from __future__ import annotations

import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs"
OUT_FILE = OUT_DIR / "ZIP知识库构建与特征可编辑推理设计文档.docx"


def p(text: str) -> str:
    return f"<w:p><w:r><w:t xml:space='preserve'>{escape(text)}</w:t></w:r></w:p>"


def h(text: str, level: int = 1) -> str:
    return (
        f"<w:p><w:pPr><w:pStyle w:val='Heading{level}'/></w:pPr>"
        f"<w:r><w:t xml:space='preserve'>{escape(text)}</w:t></w:r></w:p>"
    )


def bullet(text: str) -> str:
    return (
        "<w:p><w:pPr><w:numPr><w:ilvl w:val='0'/><w:numId w:val='1'/></w:numPr></w:pPr>"
        f"<w:r><w:t xml:space='preserve'>{escape(text)}</w:t></w:r></w:p>"
    )


def doc_xml() -> str:
    sections = [
        p("ZIP知识库构建与特征可编辑推理设计文档"),
        p("版本：v1.0"),
        p("目标：支持一个 ZIP 包内的 PDF 图纸与 XLSX 工艺表自动匹配、解析、入库、部署，并支持特征可编辑后重复推理。"),
        h("1. 背景与目标"),
        p("现有系统以单次图纸推理为主，缺少成批知识库构建能力。新的需求是把图纸与工艺数据按 ZIP 包导入，解析后追加到 vector_map_new.db 对应表中，形成可持续扩充的工艺知识库。"),
        p("知识库规模目标为约 1000 条配对数据，但不限制固定条数；一个 ZIP 包可包含多个 PDF 和一个 XLSX，XLSX 中遍历每行工艺内容，并据此匹配对应 PDF。"),
        h("2. ZIP 包约定"),
        bullet("ZIP 根目录下放置 1 个 XLSX 工艺表。"),
        bullet("同包内可放多个 PDF 图纸文件，文件名最好包含图号或可映射的唯一前缀。"),
        bullet("可选附带 samples/、README、manifest.json，用于说明字段含义和示例。"),
        bullet("系统解析时优先读取 XLSX，再按表内图号/工艺号遍历并关联 PDF。"),
        h("3. XLSX 结构"),
        p("推荐至少包含以下字段：图号、工艺名称、工序内容、备注/适用范围。系统将逐行读取，每一行视为一个候选知识条目。"),
        p("如果同一图号对应多条工艺流程，则保留为多条工艺记录，并在入库时按图号聚合到同一知识组。"),
        h("4. 解析与匹配逻辑"),
        bullet("步骤 1：解压 ZIP，校验文件数量与类型。"),
        bullet("步骤 2：读取 XLSX，逐行抽取图号和工艺内容。"),
        bullet("步骤 3：按表内图号，在 ZIP 内查找对应 PDF。"),
        bullet("步骤 4：PDF 转 PNG，调用视觉模型提取图纸特征。"),
        bullet("步骤 5：把图纸特征 + 工艺文本 + 元数据写入知识库表。"),
        bullet("步骤 6：生成批次报告，展示成功、失败、重复和冲突项。"),
        h("5. 特征可编辑与重复推理"),
        p("制造特征推理结果在前端可编辑。用户如果发现特征提取错误，可以手动修改并保存，然后再次触发工艺推理。"),
        p("该流程允许重复多次，直到用户确认结果正确。这样可以把推理从一次性输出变成可校正、可迭代的工作流。"),
        h("6. 入库策略"),
        bullet("不是查询型知识库，而是追加到现有 vector_map_new.db 同一张表中。"),
        bullet("若存在重复记录，先返回两条记录给用户选择：保留旧版或替换入库。"),
        bullet("支持冲突模式：replace、keep、skip。"),
        h("7. 工艺展示优化"),
        bullet("工艺结果按卡片分段展示，避免长文本堆叠。"),
        bullet("支持流式输出，首段生成时可先放大工艺编程卡片。"),
        bullet("任务处理中禁止页面跳转，避免中断流式展示。"),
        h("8. 建议接口"),
        bullet("POST /api/kb/import_zip：上传 ZIP 并解析。"),
        bullet("GET /api/kb/import_status/<batch_id>：查询批次状态。"),
        bullet("POST /api/kb/deploy/<batch_id>：解析成功后部署知识库。"),
        bullet("POST /api/kb/reprocess：基于编辑后的特征重新推理工艺。"),
        h("9. 错误处理"),
        bullet("XLSX 缺少必填列时，返回明确原因。"),
        bullet("PDF 未找到对应工艺或图号时，记录到失败清单。"),
        bullet("视觉模型失败时，保留原始输入和中间结果，便于重试。"),
        h("10. 自测建议"),
        bullet("准备一个示例 ZIP：1 个 XLSX + 2~3 个 PDF。"),
        bullet("检查解析后的条目数是否与表格行数一致。"),
        bullet("检查重复图号时是否能返回冲突项供用户选择。"),
        bullet("检查部署后是否写入 vector_map_new.db 的目标表。"),
        p(f"生成时间：{datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}")
    ]
    body = "".join(sections) + "<w:sectPr><w:pgSz w:w='12240' w:h='15840'/><w:pgMar w:top='1440' w:right='1440' w:bottom='1440' w:left='1440'/></w:sectPr>"
    return (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )


def content_types() -> str:
    return (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
        "<Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>"
        "<Default Extension='xml' ContentType='application/xml'/>"
        "<Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>"
        "<Override PartName='/word/styles.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml'/>"
        "<Override PartName='/docProps/core.xml' ContentType='application/vnd.openxmlformats-package.core-properties+xml'/>"
        "<Override PartName='/docProps/app.xml' ContentType='application/vnd.openxmlformats-officedocument.extended-properties+xml'/>"
        "</Types>"
    )


def rels() -> str:
    return (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
        "<Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/>"
        "</Relationships>"
    )


def document_rels() -> str:
    return (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'/>"
    )


def styles_xml() -> str:
    return (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<w:styles xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        "<w:style w:type='paragraph' w:default='1' w:styleId='Normal'>"
        "<w:name w:val='Normal'/><w:qFormat/><w:rPr><w:rFonts w:ascii='Arial' w:hAnsi='Arial'/><w:sz w:val='21'/></w:rPr>"
        "</w:style>"
        "<w:style w:type='paragraph' w:styleId='Heading1'><w:name w:val='heading 1'/><w:basedOn w:val='Normal'/><w:next w:val='Normal'/><w:qFormat/><w:pPr><w:outlineLvl w:val='0'/></w:pPr><w:rPr><w:b/><w:rFonts w:ascii='Arial' w:hAnsi='Arial'/><w:sz w:val='28'/></w:rPr></w:style>"
        "<w:style w:type='paragraph' w:styleId='Heading2'><w:name w:val='heading 2'/><w:basedOn w:val='Normal'/><w:next w:val='Normal'/><w:qFormat/><w:pPr><w:outlineLvl w:val='1'/></w:pPr><w:rPr><w:b/><w:rFonts w:ascii='Arial' w:hAnsi='Arial'/><w:sz w:val='24'/></w:rPr></w:style>"
        "</w:styles>"
    )


def core_xml() -> str:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
    return (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<cp:coreProperties xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties'"
        " xmlns:dc='http://purl.org/dc/elements/1.1/' xmlns:dcterms='http://purl.org/dc/terms/'"
        " xmlns:dcmitype='http://purl.org/dc/dcmitype/' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'>"
        "<dc:title>ZIP知识库构建与特征可编辑推理设计文档</dc:title>"
        "<dc:creator>Sisyphus</dc:creator>"
        "<cp:lastModifiedBy>Sisyphus</cp:lastModifiedBy>"
        f"<dcterms:created xsi:type='dcterms:W3CDTF'>{now}</dcterms:created>"
        f"<dcterms:modified xsi:type='dcterms:W3CDTF'>{now}</dcterms:modified>"
        "</cp:coreProperties>"
    )


def app_xml() -> str:
    return (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<Properties xmlns='http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'"
        " xmlns:vt='http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes'>"
        "<Application>Microsoft Office Word</Application></Properties>"
    )


def build_docx() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT_FILE, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types())
        zf.writestr("_rels/.rels", rels())
        zf.writestr("word/document.xml", doc_xml())
        zf.writestr("word/_rels/document.xml.rels", document_rels())
        zf.writestr("word/styles.xml", styles_xml())
        zf.writestr("docProps/core.xml", core_xml())
        zf.writestr("docProps/app.xml", app_xml())


if __name__ == "__main__":
    build_docx()
    print(str(OUT_FILE))
