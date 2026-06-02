# -*- coding: utf-8 -*-
"""规则引擎 - 从 OCR 文本中确定性提取字段"""

import re
from typing import Dict, List, Set


class DrawingRuleEngine:
    """工程图纸规则提取引擎"""

    def __init__(self):
        # 技术要求关键字
        self.tech_keywords = [
            '未注倒角', '未注圆角', '未注尺寸公差', '未注形位公差',
            '未注粗糙度', '未注热处理', '未注探伤', '未注表面处理',
            '未注焊接', '未注检验', '螺纹锁固胶', '把合力矩',
        ]

        # --- 图号 ---
        # 优先找右下角格式: 1Fxxxxx, Dxxx-xxxxx, 厂标编号xx-xxxxxxxx-xx
        self.drawing_no_patterns = [
            # 1F17810 类 (字母开头 + 数字，真实图号)
            re.compile(r'(?<!\w)([A-Z]\d{5,8})(?!\w)'),
            # 厂标编号: 20-50210001-11
            re.compile(r'(?<!\w)(\d{2}-\d{5,10}(?:-\d+)?)(?!\w)'),
            # D125A-181200A003 类
            re.compile(r'(?<!\w)([A-Z]\d{2,}[A-Z]?-\d+[A-Z]?(?!\w))'),
            # 1Fxxxxx
            re.compile(r'(?<!\w)(1F\d{5,})(?!\w)'),
            # 通用字母前缀数字后缀
            re.compile(r'(?<!\w)([A-Z]\d{2,}[-]\d+)(?!\w)'),
        ]

        # --- 螺纹 ---
        # M16 → 保留完整匹配，提取组1时补M前缀
        self.thread_patterns = [
            re.compile(r'\b(M\d+(?:[×x]\d+)?)\b'),          # M6, M16, M8×1.25
            re.compile(r'\b(T\d+(?:[×x]\d+)?)\b'),          # T8
            re.compile(r'\b(\d+(?:\.\d+)?"-?\d+UN)\b', re.IGNORECASE),  # 5 1/2"-8UN
            re.compile(r'\b(\d+-M\d+)\b'),                   # 8-M42
        ]

        # --- 孔径 Ø + 数量 ---
        # 4-Ø8, 4-φ8, Ø10, 4-Φ8
        self.hole_patterns = [
            re.compile(r'\b(\d+[-\s]*[ØφΦ]\d+(?:\.\d+)?)\b'),   # 4-Ø8, 4-φ8
            re.compile(r'(?<!\w)([ØφΦ]\d+(?:\.\d+)?)(?!\w)'),    # Ø10 单独
        ]

        # --- 公差 ±0.02 ---
        # 限制: 只匹配小数形式(≤2位数)，避免误匹配大数字
        self.tolerance_patterns = [
            re.compile(r'[±±+-](\d+(?:\.\d+)?)\b'),
            re.compile(r'([+-]?\d+(?:\.\d+)?)\s*(?:公差|tolerance)', re.IGNORECASE),
        ]

        # --- 倒角 C2, 6×45° ---
        self.chamfer_patterns = [
            re.compile(r'\bC(\d+(?:\.\d+)?)\b'),
            re.compile(r'\b(\d+(?:\.\d+)?)\s*[×x×]\s*45°'),
            re.compile(r'倒角\s*[Cс]?(\d+(?:\.\d+)?)', re.IGNORECASE),
            re.compile(r'\b(\d+[-\s]*[×x×]\s*45°)\b'),
        ]

        # --- 圆角 R5 ---
        self.radius_patterns = [
            re.compile(r'圆角\s*R(\d+)', re.IGNORECASE),
            re.compile(r'\bR(\d+(?:\.\d+)?)\b'),
        ]

        # --- 粗糙度 Ra1.6 ---
        self.roughness_patterns = [
            re.compile(r'\bRa(\d+(?:\.\d+)?)\b', re.IGNORECASE),
            re.compile(r'粗糙度\s*Ra(\d+(?:\.\d+)?)', re.IGNORECASE),
        ]

        # --- 热处理 ---
        self.heat_treat_patterns = [
            re.compile(r'HB(\d+)[~-](\d+)', re.IGNORECASE),
            re.compile(r'HRC(\d+)[~-](\d+)', re.IGNORECASE),
            re.compile(r'硬度\s*H[BRC]?(\d+)', re.IGNORECASE),
        ]

        # --- 数量/均布 EQ SP, 周均布18处 ---
        self.quantifier_patterns = [
            re.compile(r'\bEQ\s+SP\b', re.IGNORECASE),
            re.compile(r'周均布\s*(\d+)\s*处', re.IGNORECASE),
            re.compile(r'圆周均布\s*(\d+)\s*处', re.IGNORECASE),
            re.compile(r'均布\s*(\d+)\s*处', re.IGNORECASE),
            re.compile(r'\b(\d+)\s*处\b'),
        ]

        # --- 尺寸 Φxx, Rxx, 单纯数字尺寸 ---
        self.dim_phi_patterns = [
            re.compile(r'[ØφΦ]\s*(\d+(?:\.\d+)?)\b'),
        ]
        self.dim_r_patterns = [
            re.compile(r'\bR(\d+(?:\.\d+)?)\b'),
        ]

    def extract_drawing_no(self, text: str) -> str:
        """提取图号 - 跳过工号格式（20-xxxxxxxx-xx），找真实图号"""
        # 排除工号格式: 20-xxxxxxxx-xx
        工号_pattern = re.compile(r'(?<!\w)\d{2}-\d{5,10}(?:-\d+)?(?!\w)')
        # 真实图号: 字母开头 + 5-8位数字，如 1F17810
        m = re.search(r'(?<!\w)([A-Z]\d{5,8})(?!\w)', text)
        if m:
            val = m.group(1)
            if not 工号_pattern.fullmatch(val):
                return val

        # 厂标等标准格式: D125A-181200A003
        m = re.search(r'(?<!\w)([A-Z]\d{2,}[A-Z]?-\d+[A-Z]?(?!\w))', text)
        if m:
            return m.group(1)

        return ''

    def extract_part_name(self, text: str, blocks: List[Dict]) -> str:
        """提取零件名称"""
        if not blocks:
            return ''
        for block in blocks[:15]:
            t = block.get('text', '').strip()
            if 2 <= len(t) <= 25:
                skip = False
                for kw in self.tech_keywords:
                    if kw in t:
                        skip = True
                        break
                if not skip and not any(c in t for c in '：:；;'):
                    if any(k in t for k in ['加工', '零件', '轴', '法兰', '箱体', '齿轮', '盘', '盖']):
                        return t
        return ''

    def extract_tech_requirements(self, text: str) -> List[str]:
        """提取技术要求"""
        lines = []
        tech_kw_set = set(self.tech_keywords)
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            # 含技术关键字
            has_kw = any(kw in line for kw in tech_kw_set)
            # 或者是独立的公差/硬度行（非尺寸行）
            has_tolerance = bool(re.search(r'[±±+-]0\.0\d', line))
            has_hardness = bool(re.search(r'H[BRC]\d+', line, re.IGNORECASE))
            if has_kw or has_hardness:
                lines.append(line)
            elif has_tolerance and len(line) < 50:
                lines.append(line)
        return lines[:30]

    def extract_threads(self, text: str) -> List[str]:
        """提取螺纹规格"""
        threads: Set[str] = set()
        for pattern in self.thread_patterns:
            for match in pattern.finditer(text):
                val = match.group(1) if pattern.groups else match.group(0)
                if len(val) <= 20:
                    threads.add(val)
        return sorted(list(threads))

    def extract_holes(self, text: str) -> List[str]:
        """提取孔径（带数量: 4-Ø8，单个: Ø10）"""
        holes: Set[str] = set()
        for pattern in self.hole_patterns:
            for match in pattern.finditer(text):
                val = match.group(1)
                if re.match(r'^\d+$', val):
                    continue
                holes.add(val)
        return sorted(list(holes))

    def extract_tolerances(self, text: str) -> List[str]:
        """提取公差（只提取数值≤1的小数，区分于尺寸）"""
        tols: Set[str] = set()
        for pattern in self.tolerance_patterns:
            for match in pattern.finditer(text):
                val_str = match.group(1)
                try:
                    val = float(val_str)
                    if val > 1:
                        continue
                except ValueError:
                    continue
                tols.add('±' + val_str)
        return sorted(list(tols))

    def extract_dimensions(self, text: str) -> List[str]:
        """提取尺寸"""
        dims: Set[str] = set()

        # Φxx
        for m in self.dim_phi_patterns[0].finditer(text):
            dims.add('Ø' + m.group(1))

        # Rxx
        for m in self.dim_r_patterns[0].finditer(text):
            val = 'R' + m.group(1)
            dims.add(val)

        return sorted(list(dims), key=lambda x: float(re.search(r'\d+', x).group()))

    def extract_chamfers(self, text: str) -> List[str]:
        """提取倒角"""
        chamfers: Set[str] = set()
        for pattern in self.chamfer_patterns:
            for match in pattern.finditer(text):
                g = match.group(1)
                if g:
                    chamfers.add('C' + g)
        return sorted(list(chamfers))

    def extract_radii(self, text: str) -> List[str]:
        """提取圆角"""
        radii: Set[str] = set()
        for pattern in self.radius_patterns:
            for match in pattern.finditer(text):
                radii.add('R' + match.group(1))
        return sorted(list(radii))

    def extract_roughness(self, text: str) -> List[str]:
        """提取粗糙度"""
        roughness: Set[str] = set()
        for pattern in self.roughness_patterns:
            for match in pattern.finditer(text):
                roughness.add('Ra' + match.group(1))
        return sorted(list(roughness), key=lambda x: float(x[2:]))

    def extract_heat_treatment(self, text: str) -> str:
        """提取热处理要求"""
        for pattern in self.heat_treat_patterns:
            for match in pattern.finditer(text):
                g = match.groups()
                if 'HB' in pattern.pattern.upper():
                    return f'HB{g[0]}~{g[1]}'
                return f'HRC{g[0]}~{g[1]}'
        return ''

    def extract_detection(self, text: str) -> str:
        """提取探伤要求"""
        text_lower = text.lower()
        checks = ['超声波探伤', '磁粉探伤', '渗透探伤', '射线探伤', '涡流探伤']
        for kw in checks:
            if kw in text:
                return kw
        return ''

    def extract_quantifiers(self, text: str) -> List[str]:
        """提取数量/均布标记"""
        quants: Set[str] = set()
        for pattern in self.quantifier_patterns:
            for match in pattern.finditer(text):
                g = match.group(1)
                if g and g.isdigit():
                    quants.add(f'{g}处均布')
                else:
                    quants.add(match.group(0))
        # EQ SP 单独处理
        if re.search(r'\bEQ\s+SP\b', text, re.IGNORECASE):
            quants.add('EQ SP')
        return sorted(list(quants))

    def extract_all(self, text: str, blocks: List[Dict]) -> Dict:
        """提取所有字段"""
        return {
            '图号': self.extract_drawing_no(text),
            '零件名称': self.extract_part_name(text, blocks),
            '技术要求': self.extract_tech_requirements(text),
            '螺纹与螺孔': self.extract_threads(text),
            '孔径': self.extract_holes(text),
            '尺寸': self.extract_dimensions(text),
            '公差': self.extract_tolerances(text),
            '倒角': self.extract_chamfers(text),
            '圆角': self.extract_radii(text),
            '热处理': self.extract_heat_treatment(text),
            '探伤': self.extract_detection(text),
            '粗糙度': self.extract_roughness(text),
            '数量/均布': self.extract_quantifiers(text),
        }


def main():
    import sys
    if len(sys.argv) < 2:
        print("用法: python rule_engine.py <ocr文本文件路径>")
        sys.exit(1)

    ocr_file = sys.argv[1]
    with open(ocr_file, 'r', encoding='utf-8') as f:
        text = f.read()

    engine = DrawingRuleEngine()
    result = engine.extract_all(text, [])

    print("=" * 60)
    print("规则引擎提取结果")
    print("=" * 60)

    for key, value in result.items():
        if value:
            if isinstance(value, list):
                print(f"\n{key}:")
                for v in value:
                    print(f"  - {v}")
            else:
                print(f"\n{key}: {value}")


if __name__ == "__main__":
    main()
