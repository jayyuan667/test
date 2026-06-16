"""快速测试 VLM / LLM API 连通性和 token 有效性。"""

import os
import sys
import time
from dotenv import load_dotenv

# 加载 .env（自动处理引号和注释）
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI, APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError


def test_api(name: str, api_key: str, base_url: str, model: str):
    print(f"\n{'='*50}")
    print(f"测试 {name}")
    print(f"  base_url = {base_url}")
    print(f"  model    = {model}")
    print(f"  api_key  = {api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else f"  api_key  = (太短或为空)")
    print(f"{'='*50}")

    if not api_key or api_key.startswith("your-"):
        print(f"[SKIP] {name} API_KEY 未配置或为占位符")
        return False
    if not base_url:
        print(f"[SKIP] {name} BASE_URL 未配置")
        return False
    if not model:
        print(f"[SKIP] {name} MODEL 未配置")
        return False

    client = OpenAI(api_key=api_key, base_url=base_url)
    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": '你好，请回复"OK"两个字。'}],
            max_tokens=10,
            timeout=30,
        )
        elapsed = time.time() - t0
        content = resp.choices[0].message.content.strip()
        print(f"[OK] 响应成功 ({elapsed:.1f}s)")
        print(f"  回复: {content}")
        return True
    except AuthenticationError as e:
        print(f"[FAIL] 认证失败 — API Key 无效或已过期")
        print(f"  {e}")
        return False
    except RateLimitError as e:
        print(f"[WARN] 限流 — Key 有效但触发频率限制")
        print(f"  {e}")
        return True  # Key 有效，只是限流
    except APIConnectionError as e:
        print(f"[FAIL] 连接失败 — 网络/代理问题")
        print(f"  {e}")
        return False
    except APITimeoutError as e:
        print(f"[FAIL] 超时 (30s)")
        print(f"  {e}")
        return False
    except Exception as e:
        print(f"[FAIL] 未知错误: {type(e).__name__}")
        print(f"  {e}")
        return False


def main():
    results = []

    # VLM (视觉模型)
    results.append(test_api(
        "VLM (视觉模型)",
        os.getenv("VISION_API_KEY", ""),
        os.getenv("VISION_API_BASE", ""),
        os.getenv("VISION_MODEL_ID", "").replace("model_id=", "").strip(),
    ))

    # LLM (语言模型)
    results.append(test_api(
        "LLM (语言模型)",
        os.getenv("LLM_API_KEY", ""),
        os.getenv("LLM_BASE_URL", ""),
        os.getenv("LLM_MODEL", ""),
    ))

    # Embedding (可选)
    emb_key = os.getenv("EMBEDDING_API_KEY", "")
    emb_url = os.getenv("EMBEDDING_BASE_URL", "")
    emb_model = os.getenv("EMBEDDING_MODEL", "")
    if emb_key and emb_url and emb_model:
        # Embedding 用不同的调用方式
        print(f"\n{'='*50}")
        print(f"测试 Embedding API")
        print(f"  base_url = {emb_url}")
        print(f"  model    = {emb_model}")
        print(f"{'='*50}")
        client = OpenAI(api_key=emb_key, base_url=emb_url)
        t0 = time.time()
        try:
            resp = client.embeddings.create(
                model=emb_model,
                input=["测试文本"],
            )
            elapsed = time.time() - t0
            dim = len(resp.data[0].embedding)
            print(f"[OK] 响应成功 ({elapsed:.1f}s)，维度={dim}")
            results.append(True)
        except Exception as e:
            print(f"[FAIL] {type(e).__name__}: {e}")
            results.append(False)

    print(f"\n{'='*50}")
    print("总结:")
    passed = sum(results)
    total = len(results)
    print(f"  通过 {passed}/{total}")
    if passed < total:
        print("  有 API 连接失败，请检查 .env 配置和网络/代理")
        sys.exit(1)
    else:
        print("  所有 API 连接正常")


if __name__ == "__main__":
    main()
