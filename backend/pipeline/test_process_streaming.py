from types import SimpleNamespace

from backend.pipeline.process_gen import ProcessGenerator


class _FakeStreamingClient:
    def __init__(self, chunks):
        self._chunks = chunks

    def stream(self, _messages):
        for chunk in self._chunks:
            yield SimpleNamespace(content=chunk)


def test_stream_llm_response_emits_structured_rows_incrementally():
    generator = ProcessGenerator.__new__(ProcessGenerator)
    generator.llm_client = _FakeStreamingClient(
        [
            "## 生成的工艺规程\n",
            "- 0010: 备料，按图纸材料下料 （工种：料）\n",
            "- 0020: 粗车外圆，留精加工余量",
            " （工种：车）\n",
        ]
    )
    emitted = []

    final_text = generator._stream_llm_response(
        "prompt",
        process_row_callback=lambda row, index: emitted.append((index, row)),
    )

    assert "0010" in final_text
    assert emitted == [
        (0, ["0010", "料", "备料，按图纸材料下料"]),
        (1, ["0020", "车", "粗车外圆，留精加工余量"]),
    ]
