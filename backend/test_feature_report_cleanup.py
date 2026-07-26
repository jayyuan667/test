from backend.feature_report import build_feature_report


def test_feature_report_strips_explanations_from_dimension_and_blank_fields():
    report = build_feature_report(
        [
            {
                "description": "\n".join(
                    [
                        "【外形尺寸】200mm×200mm×5mm，非圆形板状零件，尺寸线覆盖整个零件外轮廓",
                        "【毛坯类型】AL2A12；无；板料，依据：零件为扁平方形板结构",
                    ]
                )
            }
        ],
        prefix_hint="Y5",
        total_pages=1,
    )

    text = report["report_text"]
    field_lines = [
        line for line in text.splitlines()
        if line.startswith(("【外形尺寸】", "【毛坯类型】", "【标识与检验】"))
    ]
    field_text = "\n".join(field_lines)

    assert "【外形尺寸】200mm×200mm×5mm" in field_text
    assert "非圆形板状零件" not in field_text
    assert "【毛坯类型】AL2A12；板料" in field_text
    assert "依据：" not in field_text


def test_feature_report_keeps_marking_field_empty_when_only_tolerance_noise():
    report = build_feature_report(
        [
            {
                "description": "【标识与检验】其余表面粗糙度Ra3.2；线性尺寸未注公差GB/T1804-m；未注孔位公差±0.02；无"
            }
        ],
        prefix_hint="Y5",
        total_pages=1,
    )

    assert "【标识与检验】无" in report["report_text"]
