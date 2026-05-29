# -*- coding: utf-8 -*-
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.pipeline.geometry_analyzer import derive_blank_spec


def _make_geo(shape, x, y, z, cylinder_radii=None):
    faces = []
    for r in (cylinder_radii or []):
        faces.append({"type_name": "Cylinder", "params": {"radius": r}, "area": 100.0})
    return {
        "shape_class": shape,
        "dimensions": {"x": x, "y": y, "z": z},
        "faces": faces,
    }


def test_plate_thickness_is_min_dim():
    geo = _make_geo("板类", x=250.0, y=100.0, z=30.0)
    assert derive_blank_spec(geo) == "δ30×250×100=1"


def test_plate_orientation_invariant():
    geo = _make_geo("板类", x=30.0, y=250.0, z=100.0)
    assert derive_blank_spec(geo) == "δ30×250×100=1"


def test_shaft_uses_max_cylinder_radius():
    geo = _make_geo("轴类", x=80.0, y=80.0, z=320.0, cylinder_radii=[40.0, 35.0])
    assert derive_blank_spec(geo) == "φ80×320=1"


def test_shaft_no_cylinder_falls_back_to_box():
    geo = _make_geo("轴类", x=80.0, y=80.0, z=320.0, cylinder_radii=[])
    assert derive_blank_spec(geo) == "320×80×80=1"


def test_disc_uses_min_dim_as_height():
    geo = _make_geo("盘类", x=120.0, y=120.0, z=40.0, cylinder_radii=[60.0])
    assert derive_blank_spec(geo) == "φ120×40=1"


def test_box_sorted_descending():
    geo = _make_geo("箱体类", x=100.0, y=200.0, z=150.0)
    assert derive_blank_spec(geo) == "200×150×100=1"


def test_general_part():
    geo = _make_geo("一般件", x=50.0, y=80.0, z=120.0)
    assert derive_blank_spec(geo) == "120×80×50=1"


def test_empty_dict_returns_empty():
    assert derive_blank_spec({}) == ""


def test_error_key_returns_empty():
    assert derive_blank_spec({"error": "FreeCAD not available"}) == ""


def test_integer_formatting():
    geo = _make_geo("板类", x=250.0, y=100.0, z=30.0)
    result = derive_blank_spec(geo)
    assert "30.0" not in result
    assert "250.0" not in result
