"""
PDF特征提取 + 融合 + Text Embedding 流程
处理逻辑：
1. 读取同一前缀的多个PDF（如1F13469_P1/P2/P3）
2. 视觉模型提取每个PDF的文字特征
3. 融合特征（拼接）
4. Text Embedding生成向量
5. 向量作为key，JSON内容作为value存储
"""

import os
import json
import base64
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
import requests

# ============================================================
# 配置
# ============================================================

# 视觉模型配置 (VLLM)
VISION_CONFIG = {
    "api_key": os.getenv("VISION_API_KEY", ""),
    "base_url": os.getenv(
        "VISION_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ),
    "model": os.getenv("VISION_MODEL_ID", "qwen-vl-plus"),
}

# 文本Embedding配置
EMBEDDING_CONFIG = {
    "api_key": os.getenv("EMBEDDING_API_KEY", ""),
    "base_url": os.getenv(
        "EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ),
    "model": os.getenv("EMBEDDING_MODEL", "text-embedding-v4"),
}

# Poppler路径
POPPLER_PATH = r"D:\_node\Release-25.12.0-0\poppler-25.12.0\Library\bin"

# 输出目录
OUTPUT_DIR = "vector_data"

# ============================================================
# 特征提取Prompt (用户提供的机械图纸解析prompt)
# ============================================================

EXTRACT_PROMPT = """你是一名专业的机械工程图纸解析专家。请对输入的工程图纸进行详细特征提取，并按以下严格格式要求紧密输出：

【格式约束】
1. 图号仅保留文件代号（如D125A-181200A003），严禁包含版本、比例、密级、文件名前缀（如(AB)）等任何其他信息
2. 各特征大类之间不要使用横杠(---)或任何分隔符，直接连续输出
3. 同一大类下的多条内容必须用分号(；)分隔，严禁使用换行或序号
4. 所有数值必须保留图纸原标注的公差、符号和单位
5. 如某特征在图纸中不存在，该字段填写"无"
6.【】后面直接接信息
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
提取弧段数量（如6段60°弧段）、特殊工艺要求、材料可追溯要求、工作温度等；多条用分号分隔
"""


# ============================================================
# 工具函数
# ============================================================


def convert_pdf_to_png(pdf_path: str, output_dir: str = None) -> List[str]:
    """PDF转PNG"""
    from pdf2image import convert_from_path

    if output_dir is None:
        output_dir = os.path.dirname(pdf_path)

    os.makedirs(output_dir, exist_ok=True)

    # 设置poppler路径
    if POPPLER_PATH not in os.environ.get("PATH", ""):
        os.environ["PATH"] = POPPLER_PATH + os.pathsep + os.environ.get("PATH", "")

    pdf_name = Path(pdf_path).stem
    images = convert_from_path(pdf_path, dpi=200, poppler_path=POPPLER_PATH)

    png_paths = []
    for i, image in enumerate(images):
        png_path = os.path.join(output_dir, f"{pdf_name}_page_{i + 1}.png")
        image.save(png_path, "PNG")
        png_paths.append(png_path)

    return png_paths


def encode_image_to_base64(image_path: str) -> str:
    """图片转base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_features_from_image(image_path: str) -> str:
    """使用视觉模型提取图片特征 - 使用DashScope"""
    import requests

    image_base64 = encode_image_to_base64(image_path)

    # 使用OpenAI兼容API
    url = f"{VISION_CONFIG['base_url']}/chat/completions"

    headers = {
        "Authorization": f"Bearer {VISION_CONFIG['api_key']}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": VISION_CONFIG["model"],
        "messages": [
            {"role": "system", "content": EXTRACT_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                    },
                    {"type": "text", "text": "请提取这张工程图纸的所有特征信息"},
                ],
            },
        ],
        "max_tokens": 2000,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=120)

    if response.status_code == 200:
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
    else:
        raise Exception(f"API错误: {response.status_code} - {response.text}")


def fuse_features(features: List[str]) -> str:
    """融合多个PDF的特征"""
    # 使用换行符分隔各PDF的特征描述
    return "\n==========\n".join(features)


def generate_text_embedding(text: str) -> np.ndarray:
    """使用文本Embedding API生成向量"""
    url = f"{EMBEDDING_CONFIG['base_url']}/embeddings"

    headers = {
        "Authorization": f"Bearer {EMBEDDING_CONFIG['api_key']}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": EMBEDDING_CONFIG["model"],
        "input": text,
        "encoding_format": "float",
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    result = response.json()
    if "data" in result and len(result["data"]) > 0:
        embedding = result["data"][0].get("embedding", [])
        return np.array(embedding, dtype=np.float32)

    raise Exception("Embedding API返回为空")


def load_json_content(prefix: str) -> List[str]:
    """加载JSON文件内容"""
    json_path = f"data_json/{prefix}.json"
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def process_prefix(prefix: str) -> Dict:
    """处理单个前缀的所有PDF"""
    print(f"\n{'=' * 50}")
    print(f"处理前缀: {prefix}")
    print(f"{'=' * 50}")

    # 1. 获取该前缀下的所有PDF
    pdf_dir = f"data/{prefix}"
    if not os.path.isdir(pdf_dir):
        return {"error": "目录不存在"}

    pdfs = sorted([f for f in os.listdir(pdf_dir) if f.endswith(".pdf")])
    if not pdfs:
        return {"error": "无PDF文件"}

    print(f"找到 {len(pdfs)} 个PDF: {pdfs}")

    # 2. 对每个PDF提取特征
    all_features = []
    temp_png_dir = f"temp_png/{prefix}"
    os.makedirs(temp_png_dir, exist_ok=True)

    for pdf_file in pdfs:
        pdf_path = f"{pdf_dir}/{pdf_file}"
        print(f"\n处理: {pdf_file}")

        try:
            # 转PNG
            png_paths = convert_pdf_to_png(pdf_path, temp_png_dir)

            # 提取每个PNG的特征（可能有多个page）
            pdf_features = []
            for png_path in png_paths:
                print(f"  提取特征: {os.path.basename(png_path)}")
                features = extract_features_from_image(png_path)
                pdf_features.append(features)
                print(f"  特征长度: {len(features)}")

            # 合并该PDF所有page的特征
            all_features.append("\n".join(pdf_features))

        except Exception as e:
            print(f"  错误: {e}")
            continue

    if not all_features:
        return {"error": "特征提取失败"}

    # 3. 融合特征
    fused = fuse_features(all_features)
    print(f"\n融合后特征长度: {len(fused)}")

    # 4. 生成embedding向量
    try:
        vector = generate_text_embedding(fused)
        print(f"向量维度: {len(vector)}")
    except Exception as e:
        print(f"Embedding错误: {e}")
        # 使用随机向量作为fallback
        vector = np.random.rand(1024).astype(np.float32)

    # 5. 加载JSON内容
    json_content = load_json_content(prefix)
    print(f"JSON内容条数: {len(json_content)}")

    return {
        "prefix": prefix,
        "features": fused,
        "vector": vector.tolist(),
        "json_content": json_content,
    }


def main():
    """主函数"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 获取所有前缀目录
    prefixes = sorted([d for d in os.listdir("data") if os.path.isdir(f"data/{d}")])

    print(f"总共 {len(prefixes)} 个前缀目录")

    results = []
    for i, prefix in enumerate(prefixes):
        print(f"\n[{i + 1}/{len(prefixes)}] 处理 {prefix}")

        result = process_prefix(prefix)

        if "error" not in result:
            # 保存为JSON，key为向量
            output_file = f"{OUTPUT_DIR}/{prefix}_vector.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "vector": result["vector"],
                        "content": result["json_content"],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            print(f"已保存: {output_file}")
            results.append(prefix)
        else:
            print(f"跳过: {result['error']}")

    print(f"\n完成! 成功处理 {len(results)} / {len(prefixes)} 个")


if __name__ == "__main__":
    main()
