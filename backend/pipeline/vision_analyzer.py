# -*- coding: utf-8 -*-
"""Vision analysis step using multi-modal vision model."""

import os
import io
import base64
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
from datetime import datetime
from openai import OpenAI
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)
from PIL import Image, ImageFilter

from ..config import create_openai_client, validate_vision_config


_DEFAULT_VISION_MAX_IMAGE_PIXELS = 34_000_000
_DEFAULT_VISION_MAX_IMAGE_BYTES = 9_500_000
_MIN_JPEG_QUALITY = 70


# ── 双模并行提示词 ────────────────────────────────────────────────
# Call 1：文字读取（所有页面，纯文字抄录模式）
_PROMPT_TEXT_EXTRACTION = """
你是专业机械工程图纸文字读取专家。逐页扫描所有图片，按以下字段原样抄录图纸中的文字和数字标注。

【图号】仅填文件代号（如 D125A-181200A003）；无则填"无"
【零件名称】标题栏中的名称；无则填"无"
【材料】材料牌号；无则填"无"
【毛坯类型】锻件/铸件/棒料等；无则填"无"
【技术要求】原文条目，多条用分号分隔；无则填"无"
【关键尺寸】所有尺寸标注（带公差保留公差），多条用分号分隔；无则填"无"
【弧段与齿形】圆弧分度、齿形参数、滚花参数、齿距、模数等；无则填"无"
【端面与平面】端面特征、基准面、配合面描述；无则填"无"
【外圆与内孔】外圆直径及公差、内孔直径及公差；无则填"无"
【螺纹与螺孔】规格（如M6×1、5½"-8UN-2A）+数量+深度；多条用分号分隔；无则填"无"
【倒角】所有倒角尺寸，多条用分号分隔；无则填"无"
【线切割】有则填具体要求；无则填"无"
【热处理与探伤】硬度要求/热处理工艺/探伤检测，多条用分号分隔；无则填"无"
【标识与检验】粗糙度要求（Ra/Rz 值及未注说明）、打印标识要求、检验标准；无则填"无"
【精度与检测特征】形位公差框格内容（类型符号+值+基准）+ 线性公差说明；多条用分号分隔；无则填"无"
【表面处理与镀层特征】阳极化/镀层/发黑/喷涂等；无则填"无"
【过渡特征】圆弧过渡（如R3）、锥面过渡、退刀槽；多条用分号分隔；无则填"无"
【其他特征】零件数量、材料可追溯要求、特殊工艺要求等；无则填"无"
【尺寸公差】未注公差说明 + 已标注公差；多条用分号分隔；无则填"无"
【刻字】字高×深度×内容；无则填"无"

规则：
- ⚠ 小数精度：φ1.8 不得写成 φ18，原样保留小数点后位数
- 所有字段必须输出，无内容填"无"，不允许省略字段
- 只抄图纸可见文字，不推断、不估算
""".strip()

# Call 2：视觉分析（所有页面，空间推理模式）
_PROMPT_VISUAL_ANALYSIS = """
你是专业机械工程图纸视觉分析专家。请综合所有页面（不要只看第一页），判断以下视觉语义字段。

【外形尺寸】
综合主视图（长宽）+ 端视图/剖视图（厚）判断整体外轮廓包络：
- 非圆形：长×宽×厚（取每方向最大外轮廓，不取台阶尺寸）
- 圆形截面：Ø直径×总长
自检：尺寸线是否跨越整个零件外轮廓？厚度是否来自端视图而非台阶高度？

【物料形态】
从以下选一：板料 / 棒料（圆） / 棒料（方） / 铸件 / 锻件 / 其他
依据：≠ 符号=板料；φ×L 格式备料=圆棒料；技术要求/标题栏注明铸/锻件

【形态】一句话描述整体几何形态（如：双端螺纹中段多阶梯光杆轴类零件）

【类型】功能类别（如：轴套类-配合件；板类-安装板）

【吊面/翻面特征】
综合所有页面检查（逐项核对）：
① 是否有仰视图且含加工特征（孔/槽/凸台）
② 剖视图中是否有开口朝下的腔槽
③ 技术要求中是否含"翻面"/"背面加工"/"反面"字样
④ 底面是否有粗糙度符号或虚线隐藏特征
⑤ 底面是否有形位公差框格引线
存在任一情形 → 填"存在，[具体描述]"；完全不存在 → 填"无"

规则：字段无内容填"无"，不允许省略字段；请综合所有页面后再输出，不要仅依据第一页
""".strip()


# System prompt for mechanical engineering drawing analysis
# 回退：设置环境变量 VISION_PROMPT_VERSION=legacy 使用旧版提示词
_VISION_SYSTEM_PROMPT_LEGACY = """你是一名专业的机械工程图纸解析专家。请对输入的工程图纸进行详细特征提取，并按以下严格格式要求紧密输出：

【格式约束】
1. 图号仅保留文件代号（如D125A-181200A003），严禁包含版本、比例、密级、文件名前缀（如(AB)）等任何其他信息
2. 各特征大类之间不要使用横杠(---)或任何分隔符，直接连续输出
3. 同一大类下的多条内容必须用分号(；)分隔，严禁使用换行或序号
4. 所有数值必须保留图纸原标注的公差、符号和单位
5. 如某特征在图纸中不存在，该字段填写"无"
6. 【】后面直接接信息

【提取字段及规则】

【图号】
仅填写文件代号（示例：D125A-181200A003）

【零件名称】
填写图纸标题栏中的零件名称

【毛坯类型】
填写毛坯类型（如锻件、铸件、棒料等）；如无明确标注填"无"

【技术要求】
原文提取所有技术要求条目；多条用分号分隔

【形态】
一句话概括零件整体几何形态（如：双端螺纹中段多阶梯光杆轴类零件；长方体板状结构）

【类型】
零件功能类别（如：紧固件-双头螺柱；密封件-汽封圈；滑动导向件-滑块）

【关键尺寸】
提取所有关键尺寸（总长、直径、长度、孔径、深度、角度等）；带公差的尺寸保留公差；多条用分号分隔

【弧段与齿形】
提取圆弧分度、齿形参数、滚花参数、齿距、模数等；多条用分号分隔

【端面与平面】
描述各端面特征、基准面、打印标识面、配合面等；多条用分号分隔

【外圆与内孔】
提取外圆直径及公差、内孔直径及公差、表面粗糙度；多条用分号分隔

【螺纹与螺孔】
提取螺纹规格（如M27×2-6H、5 1/2"-8UN-2A）、螺纹长度、旋向、精度等级；多条用分号分隔

【倒角】
提取所有倒角尺寸（如1×45°、C1.5、0.8×45°）；多条用分号分隔

【热处理与探伤】
提取硬度要求（如HB293-321、HRC43-48）、热处理工艺、无损检测要求（如超声波探伤2级、磁粉探伤）；多条用分号分隔

【标识与检验】
提取打印标识要求、检验标准、粗糙度要求；多条用分号分隔

【线切割】
填写线切割工艺要求或"无"

【精度与检测特征】
提取形位公差（如同轴度、垂直度、跳动）、线性公差；保留公差值和基准符号；多条用分号分隔

【表面处理与镀层特征】
提取表面处理（如发蓝、磷化）、镀层要求；如无填"无"

【过渡特征】
提取所有圆弧过渡（如R3.15、R0.5）、锥面过渡、退刀槽；多条用分号分隔

【其他特征】
提取弧段数量（如6段60°弧段）、特殊工艺要求、材料可追溯要求、工作温度等；多条用分号分隔"""

_VISION_SYSTEM_PROMPT_V4 = """你是一名专业的机械工程图纸解析专家。请对输入的工程图纸进行详细特征提取，并按以下严格格式要求紧密输出：

【格式约束】
1. 图号仅保留文件代号（如D125A-181200A003），严禁包含版本、比例、密级、文件名前缀（如(AB)）等任何其他信息
2. 各特征大类之间不要使用横杠(---)或任何分隔符，直接连续输出
3. 同一大类下的多条内容必须用分号(；)分隔，严禁使用换行或序号
4. 所有数值必须保留图纸原标注的公差、符号和单位
5. 如某特征在图纸中不存在，该字段填写"无"
6. 【】后面直接接信息
7. ⚠ 小数点精度：数字中的小数点及其后位数必须原样保留，禁止丢失或省略
   - 错误示例：φ1.8 写成 φ18（漏掉小数点，差10倍）；φ3.8 写成 φ38
   - 正确示例：φ1.8 写 φ1.8；φ3.8 写 φ3.8

【提取字段及规则】

【图号】
仅填写文件代号（示例：D125A-181200A003）

【零件名称】
填写图纸标题栏中的零件名称

【毛坯类型】
填写毛坯类型（如锻件、铸件、棒料等）；如无明确标注填"无"

【物料形态】
从以下选项中选一个填写：板料 / 棒料（圆） / 棒料（方） / 铸件 / 锻件 / 其他
识别规则：
  - 板料：图纸含 ≠ 符号（如 ≠10、≠20），≠ 后第一个数字即为板厚，板厚远小于其他两维
  - 棒料（圆）：备料/毛坯含 φ×L 格式（如 φ65×120）
  - 棒料（方）：备料/毛坯含方形截面或 □ 标注（如 40×40×240）
  - 铸件/锻件：技术要求或标题栏注明铸件、铸造、锻件、锻造
⚠ 板材厚度专项规则：当识别为板料时，≠ 后的数字是板厚，必须用于【外形尺寸】的"厚"维度；主视图中局部台阶/凸台竖向高度≠整体板厚，二者不要混淆；若图纸无 ≠ 符号，厚度从端视图（左视图/剖视图）读取；端视图中两个截面方向的尺寸判断规则见下方"槽弯形板厚度陷阱"

【技术要求】
原文提取所有技术要求条目；多条用分号分隔

【形态】
一句话概括零件整体几何形态（如：双端螺纹中段多阶梯光杆轴类零件；长方体板状结构）

【类型】
零件功能类别（如：紧固件-双头螺柱；密封件-汽封圈；滑动导向件-滑块）

【关键尺寸】
提取所有关键尺寸（总长、直径、长度、孔径、深度、角度等）；带公差的尺寸保留公差；多条用分号分隔

【外形尺寸】
第一步：判断零件截面类型
  - 圆形截面（轴/法兰/套筒，Ø符号）→ 输出 Ø直径×总厚
  - 非圆形截面（板/块/支架）→ 输出 长×宽×厚
第二步：看尺寸线位置（关键！不要只看数字）
  - 外轮廓尺寸的特征：尺寸线两端箭头指向零件最外侧边界，尺寸线跨越零件的整个宽度或长度，数字写在零件轮廓线外侧
  - 台阶/内部尺寸的特征：尺寸线两端箭头停在零件内部台阶面上，尺寸线只跨越台阶的部分宽度，不是整个零件
  - 判断口诀：尺寸线跨越整个零件 → 外形尺寸；尺寸线只跨越一部分 → 台阶尺寸，排除
第三步：分视图提取
  - 俯视图/主视图（零件的最大投影面）：提取长和宽。看零件整体外形包络线（silhouette），取该方向的最大外轮廓尺寸，不论它在哪个台阶层级。台阶层级的变动不影响外轮廓判断——即使更宽的尺寸线在下面一层台阶上（如358在376下方），只要它是该方向的最大包络，就取358而不是376
  - ⚠ 特别注意：零件若有多层台阶，平行于同一方向的尺寸可能有多条（如388和376平行，358在下面另一层）。此时必须看零件整体轮廓，取最外侧的。不能因为两条线看起来平行同层就选它们作为长宽对
  - 端视图/剖视图（侧面，截面）：提取厚度。剖视图中标注在截面视图上、垂直于板面的小数值即为板厚
  - 若同一方向在多个视图有标注，取最大值
第四步：输出格式
  - 非圆形：L×W×T（示例：388×358×13）
  - 圆形：ØD×L（示例：Ø63.17×16.4）
自检规则（输出前必须执行）：
  - □ 长和宽是否都取自尺寸线跨越整个零件外轮廓的标注？（不能从台阶/内部取）
  - □ 长和宽的比值是否 < 1.5？（方形/矩形板的长宽通常相近，若比值 > 1.5 说明其中一个取了台阶尺寸）
  - □ 厚度是否取自端视图/剖视图？（不能取自主视图的台阶高度）
  - □ 厚度是否远小于长和宽（通常 < 长/5）？（若厚度 > 长/3，说明取的是台阶高度不是板厚）
  - □ 外形尺寸的三个数字是否也出现在了【关键尺寸】列表中？（如果出现了，说明该数字是台阶尺寸，必须排除）

【弧段与齿形】
提取圆弧分度、齿形参数、滚花参数、齿距、模数等；多条用分号分隔

【端面与平面】
描述各端面特征、基准面、打印标识面、配合面等；多条用分号分隔

【外圆与内孔】
提取外圆直径及公差、内孔直径及公差、表面粗糙度；多条用分号分隔
⚠ 回转体所有同轴直径必须全部列出，不可只提一个最大/最小直径
⚠ 孔系完整性：逐视图扫描，按类型分组列出所有孔，格式：数量×规格-孔类型；示例：12×φ2.7↴φ5.6×90°沉孔；8×φ2.3↴φ4.6×90°沉孔；5×φ6.5通孔；2×φ18通孔；4×M2螺纹孔（螺纹孔同时填入【螺纹与螺孔】字段）
⚠ 小数点核验：φ2.3、φ1.8、φ2.7等小孔极易被漏识别为φ23、φ18、φ27（差10倍）；识别后必须检查：若出现φ13~φ29范围内的孔且图纸同时有密集小孔区，很可能是漏掉了小数点，需重新核对
⚠ 铣型腔 vs 钻孔：φ35、φ50等大直径圆形特征通常是铣出的圆形型腔/槽（标注"圆形铣槽φ50"），与φ2.x小钻孔是完全不同工艺，须分别列出，不要相互替代

【螺纹与螺孔】
提取螺纹规格（如M27×2-6H、5 1/2"-8UN-2A）、螺纹长度、旋向、精度等级；多条用分号分隔
⚠ 螺距未标注时在规格后标[经验值]，如"M52×1.5[经验值]"
⚠ 全视图扫描：螺纹标注常见于剖视图、局部放大图或背面视图，必须逐视图检查含"M+数字"的标注，不得只看正面主视图
⚠ M2、M3等小螺纹外观与普通小孔相似，区别在于标注前缀是"M"而非"φ"；凡带M前缀的孔必须填入本字段，不得混入【外圆与内孔】

【倒角】
提取所有倒角尺寸（如1×45°、C1.5、0.8×45°）；多条用分号分隔

【热处理与探伤】
提取硬度要求（如HB293-321、HRC43-48）、热处理工艺、无损检测要求（如超声波探伤2级、磁粉探伤）；多条用分号分隔

【标识与检验】
提取打印标识要求、检验标准、粗糙度要求；多条用分号分隔

【线切割】
填写线切割工艺要求或"无"

【精度与检测特征】
逐张扫描以下位置：
  ① 每个尺寸数字旁的公差符号（如 ±0.05、+0.02/-0.01、H7、h6、JS6）
  ② 标题栏或技术要求区的"未注公差"说明（如"未注公差按GB/T 1804-m"）
  ③ 公差框格内的极限偏差数值
  格式：尺寸值 公差；未注公差说明；如确实无任何公差标注则填"无"

【表面处理与镀层特征】
提取表面处理（如发蓝、磷化、阳极化）、镀层要求；如无填"无"

【过渡特征】
提取所有圆弧过渡（如R3.15、R0.5）、锥面过渡、退刀槽；多条用分号分隔

【其他特征】
提取弧段数量（如6段60°弧段）、特殊工艺要求、材料可追溯要求、工作温度等；多条用分号分隔

沉孔格式：nXφA↴φB×C° 解读：φA=钻孔直径（小），φB=沉孔大径，C°=锥角；不要把φB当主孔铣削直径
三维数模优先：如图纸注明"未注尺寸以三维数模为准"，在【技术要求】中记录此信息

【孔系核验（提交前必须执行，不可跳过）】
完成所有字段填写后，强制执行以下3步，发现问题立即回头修正对应字段：

第一步·小数点复查
  重新逐孔核对【外圆与内孔】中所有 φ<5 的孔径是否含小数点
  - φ2.3 ≠ φ23；φ1.8 ≠ φ18；φ2.7 ≠ φ27；φ3.8 ≠ φ38
  - 若已填写 φ13~φ29 范围的孔，而图纸存在密集小孔区，99%是漏掉了小数点
  - 修正：找到原标注，重新辨认小数点位置

第二步·螺纹孔排查
  重新扫描所有视图（正/背/左/右/剖/局部放大）
  - 找出所有"M+数字"格式标注（如 M2、M3×0.5）
  - 确认已填入【螺纹与螺孔】字段，未被误填为普通孔
  - M2螺纹孔与φ2通孔外观相近，唯一区别是标注前缀

第三步·沉孔符号确认
  检查是否有"↴"或"⌴"沉孔符号被遗漏
  - 格式 nXφA↴φB×C° 中：φA=过孔小径，φB=沉孔大径（必须单独记录）
  - 已正确分组并统计沉孔数量？核对：图纸上几种沉孔规格 = 【外圆与内孔】中几组沉孔条目

数量统计原则：逐视图独立数孔，跨视图合并时注明方向来源（正面/背面/侧面）；
  总孔数自查：(所有孔数量之和) 是否与图纸注记一致？"""

def _get_vision_system_prompt() -> str:
    version = os.getenv("VISION_PROMPT_VERSION", "v4").strip().lower()
    if version == "legacy":
        print("[Vision] 使用旧版提示词 (VISION_PROMPT_VERSION=legacy)")
        return _VISION_SYSTEM_PROMPT_LEGACY
    return _VISION_SYSTEM_PROMPT_V4

VISION_SYSTEM_PROMPT = _get_vision_system_prompt()


class VisionAnalyzer:
    """Analyzes PDF pages using vision model to extract drawing features."""

    @staticmethod
    def _classify_exception(exc: Exception) -> Dict[str, Any]:
        if isinstance(exc, APIConnectionError):
            return {"error_type": "connection_error", "retryable": True}
        if isinstance(exc, APITimeoutError):
            return {"error_type": "timeout", "retryable": True}
        if isinstance(exc, RateLimitError):
            return {"error_type": "rate_limit", "retryable": True}
        if isinstance(exc, AuthenticationError):
            return {"error_type": "authentication_error", "retryable": False}
        if isinstance(exc, InternalServerError):
            return {"error_type": "internal_server_error", "retryable": True}
        if isinstance(exc, BadRequestError):
            return {"error_type": "bad_request", "retryable": False}
        return {"error_type": type(exc).__name__, "retryable": False}

    @staticmethod
    def _should_fallback_locally(exc: Exception) -> bool:
        return isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError))

    @staticmethod
    def _normalize_base_url(base_url: str | None) -> str | None:
        if not base_url:
            return None
        value = base_url.strip()
        if not value:
            return None
        if not value.startswith(("http://", "https://")):
            value = f"https://{value}"
        return value.rstrip("/")

    def __init__(self):
        """Initialize vision analyzer with API credentials from environment."""
        config_error = validate_vision_config("doubao")
        if config_error:
            raise ValueError(config_error)

        self.api_key = os.getenv("VISION_API_KEY")
        self.base_url = self._normalize_base_url(os.getenv("VISION_API_BASE"))
        model_param = os.getenv("VISION_MODEL_ID", "")
        self.model = model_param.replace("model_id=", "").strip()
        requested_max_tokens = int(os.getenv("VISION_MAX_TOKENS", "4096"))
        self.max_tokens = min(requested_max_tokens, 4096)

        print(f"[Vision] API配置: base_url={self.base_url}, model={self.model}")

        if not self.api_key:
            print("[Vision] WARNING: VISION_API_KEY is not set!")
        if not self.base_url:
            print("[Vision] WARNING: VISION_API_BASE is not set!")
        if not self.model:
            print("[Vision] WARNING: VISION_MODEL_ID is not set!")

        self.client = create_openai_client(self.api_key, self.base_url)
        self._local_analyzer = None

    def _get_local_analyzer(self):
        if self._local_analyzer is None:
            from .local_vision_analyzer import LocalVisionAnalyzer

            self._local_analyzer = LocalVisionAnalyzer()
        return self._local_analyzer

    @staticmethod
    def _env_positive_int(name: str, default: int) -> int:
        try:
            value = int(os.getenv(name, str(default)))
        except (TypeError, ValueError):
            return default
        return value if value > 0 else default

    @staticmethod
    def _mime_for_format(image_format: str | None) -> str:
        normalized = (image_format or "PNG").upper()
        if normalized in {"JPEG", "JPG"}:
            return "image/jpeg"
        if normalized == "WEBP":
            return "image/webp"
        return "image/png"

    @staticmethod
    def _flatten_for_jpeg(img: Image.Image) -> Image.Image:
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        return img.convert("RGB")

    @staticmethod
    def _resize_to_pixel_limit(img: Image.Image, max_pixels: int) -> Image.Image:
        pixel_count = img.width * img.height
        if pixel_count <= max_pixels:
            return img
        scale = (max_pixels / pixel_count) ** 0.5
        width = max(1, int(img.width * scale))
        height = max(1, int(img.height * scale))
        return img.resize((width, height), Image.Resampling.LANCZOS)

    def _prepare_image_payload(self, image_path: str) -> tuple[str, str]:
        """Return base64 image payload and MIME type for the vision API.

        Source images are never overwritten. Images are only re-encoded when
        sharpening is enabled, pixel count exceeds the model limit, or the
        encoded request body would exceed the configured byte limit.
        """
        with open(image_path, "rb") as f:
            raw_bytes = f.read()

        max_pixels = self._env_positive_int("VISION_MAX_IMAGE_PIXELS", _DEFAULT_VISION_MAX_IMAGE_PIXELS)
        max_bytes = self._env_positive_int("VISION_MAX_IMAGE_BYTES", _DEFAULT_VISION_MAX_IMAGE_BYTES)
        sharpen = os.getenv("VISION_SHARPEN", "1") != "0"

        with Image.open(io.BytesIO(raw_bytes)) as opened:
            image_format = opened.format or "PNG"
            source_pixels = opened.width * opened.height
            needs_resize = source_pixels > max_pixels
            needs_reencode = sharpen or needs_resize or len(raw_bytes) > max_bytes

            if not needs_reencode:
                return base64.b64encode(raw_bytes).decode("utf-8"), self._mime_for_format(image_format)

            img = opened.copy()

        img = self._resize_to_pixel_limit(img, max_pixels)
        if sharpen:
            img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=2))

        source_format = image_format.upper()
        output_format = "JPEG" if len(raw_bytes) > max_bytes or source_format in {"JPEG", "JPG"} else "PNG"

        buf = io.BytesIO()
        save_format = "JPEG" if output_format in {"JPEG", "JPG"} else output_format
        save_img = self._flatten_for_jpeg(img) if save_format == "JPEG" else img
        save_kwargs = {"quality": 90, "optimize": True} if save_format == "JPEG" else {"optimize": True}
        save_img.save(buf, format=save_format, **save_kwargs)
        payload = buf.getvalue()
        mime = self._mime_for_format(save_format)

        if len(payload) > max_bytes:
            jpeg_img = self._flatten_for_jpeg(img)
            for quality in (85, 80, 75, _MIN_JPEG_QUALITY):
                buf = io.BytesIO()
                jpeg_img.save(buf, format="JPEG", quality=quality, optimize=True)
                payload = buf.getvalue()
                mime = "image/jpeg"
                if len(payload) <= max_bytes:
                    break

        while len(payload) > max_bytes and img.width > 1 and img.height > 1:
            scale = max(0.5, ((max_bytes / len(payload)) ** 0.5) * 0.95)
            width = max(1, int(img.width * scale))
            height = max(1, int(img.height * scale))
            img = img.resize((width, height), Image.Resampling.LANCZOS)
            jpeg_img = self._flatten_for_jpeg(img)
            buf = io.BytesIO()
            jpeg_img.save(buf, format="JPEG", quality=_MIN_JPEG_QUALITY, optimize=True)
            payload = buf.getvalue()
            mime = "image/jpeg"

        return base64.b64encode(payload).decode("utf-8"), mime

    def _fallback_to_local(self, image_paths: List[str], reason: str, annotation_text: str = "") -> Dict[str, Any]:
        print(f"[Vision] Fallback to LocalVisionAnalyzer: {reason}")
        try:
            local = self._get_local_analyzer()
            if len(image_paths) == 1:
                result = local.analyze_image(image_paths[0])
            else:
                result = local.analyze_drawing(image_paths)
            result["fallback_used"] = "local"
            result["fallback_reason"] = reason
            result["degraded"] = True
            if annotation_text.strip():
                result["annotation_text"] = annotation_text.strip()
            return result
        except Exception as fallback_error:
            print(f"[Vision] Local fallback failed: {fallback_error}")
            return {
                "image_path": image_paths[0] if image_paths else "",
                "description": "",
                "timestamp": datetime.now().isoformat(),
                "ok": False,
                "error": f"{reason}; local fallback failed: {fallback_error}",
                "fallback_used": "local",
                "fallback_reason": reason,
                "degraded": True,
                "error_type": "local_fallback_failed",
                "retryable": False,
            }

    def _encode_image(self, image_path: str) -> str:
        """读取图片，必要时生成适合 VLM 输入限制的 base64 字符串。"""
        encoded, _mime = self._prepare_image_payload(image_path)
        return encoded

    def _call_vlm_batch(self, prompt: str, image_paths: List[str]) -> str:
        """将所有页面打包进一次 API 调用，返回原始文本响应。"""
        content: List[Dict] = []
        for path in image_paths:
            b64, mime = self._prepare_image_payload(path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            })
        content.append({"type": "text", "text": "请按照要求分析图纸，所有字段必须输出。"})
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content},
        ]
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    timeout=600,
                )
                return response.choices[0].message.content
            except (APIConnectionError, APITimeoutError) as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    print(f"[Vision] API 连接失败 (attempt {attempt + 1}/{max_retries})，{wait}s 后重试: {e}")
                    time.sleep(wait)
                else:
                    raise

    def analyze_drawing(self, image_paths: List[str],
                        annotation_text: str = "") -> Dict[str, Any]:
        """双模并行调用：文字读取 + 视觉分析，合并为单条结果。

        替代逐页串行的 analyze_image() 循环，速度提升 2–4 倍。
        返回格式与 analyze_image() 兼容（含 image_path / description / ok）。

        annotation_text: 可选，由 YOLO + 人工核对后的特征框生成的中文文本，
                         非空时拼到视觉分析 prompt 之前作为已知特征位置提示。
                         文字识别 prompt 不受影响（文字识别与框无关）。
        """
        print(f"[Vision] 双模并行分析，共 {len(image_paths)} 页")
        visual_prompt = _PROMPT_VISUAL_ANALYSIS
        if annotation_text.strip():
            visual_prompt = annotation_text + "\n\n" + _PROMPT_VISUAL_ANALYSIS
        try:
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_text = ex.submit(self._call_vlm_batch, _PROMPT_TEXT_EXTRACTION, image_paths)
                f_visual = ex.submit(self._call_vlm_batch, visual_prompt, image_paths)
                text_result = f_text.result()
                visual_result = f_visual.result()
            # 视觉分析结果追加在后，同名字段以视觉结果为准（_parse_structured_fields 后者覆盖前者）
            merged = f"{text_result}\n{visual_result}"
            print("[Vision] 双模并行分析完成")
            return {
                "image_path": image_paths[0] if image_paths else "",
                "description": merged,
                "timestamp": datetime.now().isoformat(),
                "ok": True,
            }
        except Exception as e:
            print(f"[Vision] 双模并行分析失败: {e}")
            import traceback
            traceback.print_exc()
            if self._should_fallback_locally(e):
                return self._fallback_to_local(image_paths, str(e), annotation_text=annotation_text)
            error_meta = self._classify_exception(e)
            return {
                "image_path": image_paths[0] if image_paths else "",
                "description": "",
                "timestamp": datetime.now().isoformat(),
                "ok": False,
                "error": str(e),
                "degraded": True,
                **error_meta,
            }

    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """Analyze a single image and extract features.

        Args:
            image_path: Path to the PNG image file

        Returns:
            Dictionary with image_path, description, and timestamp
        """
        print(f"[Vision] 开始分析图片: {image_path}")

        try:
            image_base64, mime = self._prepare_image_payload(image_path)

            messages = [
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{image_base64}"
                            },
                        },
                        {
                            "type": "text",
                            "text": "请严格按照上述格式要求详细分析这张工程图纸，提取所有特征信息，确保每个字段都填写完整。",
                        },
                    ],
                },
            ]

            print("[Vision] 发送API请求...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                timeout=600,
            )
            print("[Vision] API响应接收完成")

            description = response.choices[0].message.content
            print(f"[Vision] 分析完成: {image_path}")

            return {
                "image_path": image_path,
                "description": description,
                "timestamp": datetime.now().isoformat(),
                "ok": True,
            }

        except Exception as e:
            print(f"[Vision] ERROR分析图片失败 {image_path}: {e}")
            import traceback

            traceback.print_exc()
            if self._should_fallback_locally(e):
                return self._fallback_to_local([image_path], str(e))
            error_meta = self._classify_exception(e)
            return {
                "image_path": image_path,
                "description": "",
                "timestamp": datetime.now().isoformat(),
                "ok": False,
                "error": str(e),
                "degraded": True,
                **error_meta,
            }

    def analyze_images(self, image_paths: List[str], progress_callback=None) -> List[Dict[str, Any]]:
        """Analyze multiple images.

        Args:
            image_paths: List of paths to PNG image files
            progress_callback: Optional callback function(image_path, result) called after each image

        Returns:
            List of analysis results
        """
        print(f"[Vision] 开始分析 {len(image_paths)} 张图片")
        results = []
        for i, image_path in enumerate(image_paths):
            print(f"[Vision] 分析进度: {i+1}/{len(image_paths)}")

            # 分析前发送进度
            if progress_callback:
                progress_callback(image_path, f"正在分析第 {i+1}/{len(image_paths)} 页...")

            result = self.analyze_image(image_path)
            results.append(result)

            # 分析完成后发送完整结果（不截断）
            if progress_callback:
                desc = result.get("description", "")
                if result.get("error"):
                    desc = f"[ERROR] {result['error']}"
                progress_callback(image_path, f"第 {i+1} 页分析完成:\n{desc}")

        print("[Vision] 所有图片分析完成")
        return results
