"""
STEP Geometry Feature Extraction Module

Extract geometric features directly from STEP files using FreeCAD's built-in OpenCASCADE.
This module bypasses visual OCR for more accurate feature extraction.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# FreeCAD paths - try to use the existing FreeCAD installation
FC_LIB_PATHS = [
    os.getenv("FREECAD_LIB"),
    os.getenv("FREECAD_BIN"),
    r"D:\Program Files\FreeCAD 1.1\bin",
    r"D:\Program Files\FreeCAD 1.1\lib",
    r"C:\Program Files\FreeCAD 1.1\bin",
    r"C:\Program Files\FreeCAD 1.1\lib",
    r"C:\Program Files\FreeCAD 0.21\bin",
    r"C:\Program Files\FreeCAD 0.21\lib",
]
for path in FC_LIB_PATHS:
    if path and os.path.exists(path) and path not in sys.path:
        sys.path.append(path)

# Try to import FreeCAD, if not available, module will be disabled
try:
    import FreeCAD as App
    import Part

    FREECAD_AVAILABLE = True
except ImportError:
    FREECAD_AVAILABLE = False
    print("[geometry] FreeCAD not available, geometry mode disabled")

# Import config
_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))
try:
    from config import GEOMETRY_SETTINGS
except:
    GEOMETRY_SETTINGS = {}


def classify_face(face):
    """Classify a face by its surface type."""
    try:
        surface = face.Surface
        surface_type = type(surface).__name__

        result = {"type": surface_type, "params": {}}

        # Analyze based on surface type
        if "Plane" in surface_type:
            result["type_name"] = "Plane"
        elif "Cylinder" in surface_type:
            result["type_name"] = "Cylinder"
            result["params"]["radius"] = round(surface.Radius, 3)
        elif "Cone" in surface_type:
            result["type_name"] = "Cone"
            result["params"]["radius"] = round(surface.Radius, 3)
            result["params"]["angle"] = round(surface.Angle, 3)
        elif "Sphere" in surface_type:
            result["type_name"] = "Sphere"
            result["params"]["radius"] = round(surface.Radius, 3)
        elif "Torus" in surface_type:
            result["type_name"] = "Torus"
        elif "Bezier" in surface_type or "BSpline" in surface_type:
            result["type_name"] = "Bezier/BSpline"
        else:
            result["type_name"] = "Other"

        # Calculate area
        try:
            result["area"] = round(face.Area, 2)
        except:
            result["area"] = 0

        return result
    except Exception as e:
        return {"type": "Unknown", "type_name": "Unknown", "error": str(e)}


def _infer_thread_spec(diameter_mm: float) -> str:
    """Map a drill diameter to the most likely thread spec."""
    if diameter_mm < 1.0:
        return ""
    if diameter_mm < 1.5:
        return "M1.2"
    if diameter_mm < 2.2:
        return "M2"
    if diameter_mm < 2.8:
        return "M2.5"
    if diameter_mm < 3.5:
        return "M3"
    if diameter_mm < 4.5:
        return "M4"
    if diameter_mm < 5.5:
        return "M5"
    if diameter_mm < 6.5:
        return "M6"
    if diameter_mm < 9.0:
        return "M8"
    if diameter_mm < 11.0:
        return "M10"
    return f"M{int(round(diameter_mm))}"


def _classify_shape(dimensions: dict, face_type_counts: dict, face_count: int) -> str:
    """Classify part shape from bounding box ratios and surface distribution."""
    x, y, z = dimensions.get("x", 0), dimensions.get("y", 0), dimensions.get("z", 0)
    dims = sorted([x, y, z])
    d_min, d_mid, d_max = dims[0], dims[1], dims[2]
    if d_max < 0.001:
        return "一般件"

    cyl_count = face_type_counts.get("Cylinder", 0)
    cyl_ratio = cyl_count / face_count if face_count > 0 else 0

    if d_min / d_max < 0.15:
        return "板类"
    if d_max / max(d_mid, 0.001) > 3 and cyl_ratio > 0.15:
        return "轴类"
    if d_max / max(d_mid, 0.001) < 0.6 and d_mid / max(d_min, 0.001) < 0.6 and cyl_ratio > 0.2:
        return "盘类"
    if cyl_ratio > 0.35:
        return "回转体"
    if cyl_ratio < 0.15 and d_min / d_max > 0.3:
        return "箱体类"
    return "一般件"


def analyze_step_geometry(step_file: str) -> dict:
    """Analyze STEP file and extract geometric features."""
    if not FREECAD_AVAILABLE:
        return {"error": "FreeCAD not available"}

    if not os.path.exists(step_file):
        return {"error": f"File not found: {step_file}"}

    try:
        shape = Part.read(step_file)

        faces = shape.Faces
        face_analysis = []
        for face in faces:
            face_info = classify_face(face)
            face_analysis.append(face_info)

        edges = shape.Edges
        edge_count = len(edges)

        bound_box = shape.BoundBox
        dimensions = {
            "x": round(bound_box.XLength, 2),
            "y": round(bound_box.YLength, 2),
            "z": round(bound_box.ZLength, 2),
        }

        type_counts = {}
        for face in face_analysis:
            t = face.get("type_name", "Unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        # Volume and surface area
        try:
            volume = round(shape.Volume, 1)
        except Exception:
            volume = 0
        try:
            total_area = round(shape.Area, 1)
        except Exception:
            total_area = 0

        # Shape classification
        shape_class = _classify_shape(dimensions, type_counts, len(faces))

        # Hole feature analysis: inner cylindrical faces (negative normal direction)
        hole_radii = []
        for face in faces:
            try:
                if "Cylinder" not in type(face.Surface).__name__:
                    continue
                # Sample normal at center of face's parameter space
                u0, u1, v0, v1 = face.ParameterRange
                normal = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
                center = face.CenterOfMass
                # Vector from axis to surface center; if normal opposes it → inner (hole)
                radial = App.Vector(
                    center.x - bound_box.Center.x,
                    center.y - bound_box.Center.y,
                    center.z - bound_box.Center.z,
                )
                dot = normal.dot(radial)
                if dot < 0:  # normal points inward → this is a hole wall
                    hole_radii.append(round(face.Surface.Radius, 3))
            except Exception:
                pass

        hole_info = {}
        if hole_radii:
            diameters = sorted(set(round(r * 2, 2) for r in hole_radii))
            d_min, d_max = min(diameters), max(diameters)
            t_min = _infer_thread_spec(d_min)
            t_max = _infer_thread_spec(d_max)
            thread_range = f"{t_min}~{t_max}" if t_min != t_max else t_min
            hole_info = {
                "count": len(hole_radii),
                "min_diameter": d_min,
                "max_diameter": d_max,
                "thread_range": thread_range,
            }

        return {
            "dimensions": dimensions,
            "faces": face_analysis,
            "face_count": len(faces),
            "edge_count": edge_count,
            "face_type_counts": type_counts,
            "volume": volume,
            "total_area": total_area,
            "shape_class": shape_class,
            "hole_info": hole_info,
        }

    except Exception as e:
        return {"error": str(e)}


def extract_features_from_step(step_file: str) -> str:
    """
    Extract features from STEP file and return as text description.

    Args:
        step_file: Path to STEP file

    Returns:
        Feature description text
    """
    if not FREECAD_AVAILABLE:
        return "[Geometry mode unavailable - FreeCAD not installed]"

    if not os.path.exists(step_file):
        return f"[Error: STEP file not found: {step_file}]"

    try:
        result = analyze_step_geometry(step_file)

        if "error" in result:
            return f"[Error: {result['error']}]"

        return format_features_text(result)

    except Exception as e:
        return f"[Error: {str(e)}]"


def format_features_text(result: dict) -> str:
    """Format analysis result as readable text.

    All field values are placed on the SAME line as their 【field】 tag so that
    the regex r'【([^】]+)】([^\\n【]*)' used by the RAG pipeline can extract them.
    """
    lines = []

    dims = result.get("dimensions", {})
    if dims:
        dim_str = f"长 {dims.get('x', 0)}mm × 宽 {dims.get('y', 0)}mm × 高 {dims.get('z', 0)}mm"
        lines.append(f"【尺寸】{dim_str}")

    volume = result.get("volume", 0)
    if volume:
        lines.append(f"【体积】{volume} mm³")

    total_area = result.get("total_area", 0)
    if total_area:
        lines.append(f"【总面积】{total_area} mm²")

    shape_class = result.get("shape_class", "")
    if shape_class:
        lines.append(f"【形状分类】{shape_class}")

    face_count = result.get("face_count", 0)
    edge_count = result.get("edge_count", 0)
    face_types = result.get("face_type_counts", {})
    type_str = (", ".join(f"{k}:{v}" for k, v in face_types.items())) if face_types else ""
    geo_val = f"面数:{face_count}; 边数:{edge_count}" + (f"; 面类型:{type_str}" if type_str else "")
    lines.append(f"【几何特征】{geo_val}")

    faces = result.get("faces", [])
    if faces:
        cylinders = [f for f in faces if f.get("type_name") == "Cylinder"]
        planes = [f for f in faces if f.get("type_name") == "Plane"]

        if cylinders:
            cyl_parts = []
            for i, cyl in enumerate(cylinders[:5], 1):
                r = cyl.get("params", {}).get("radius", 0)
                cyl_parts.append(f"圆柱面{i}:半径{r}mm")
            lines.append(f"【圆柱面特征】{'; '.join(cyl_parts)}")

        if planes:
            total_plane_area = sum(p.get("area", 0) for p in planes)
            lines.append(f"【平面特征】平面数量:{len(planes)},总面积:{total_plane_area:.1f}mm²")

    hole_info = result.get("hole_info", {})
    if hole_info:
        h = hole_info
        hole_str = (
            f"孔数量:{h['count']}; "
            f"最小孔径:{h['min_diameter']}mm; "
            f"最大孔径:{h['max_diameter']}mm; "
            f"推测螺纹:{h['thread_range']}"
        )
        lines.append(f"【孔特征】{hole_str}")

    return "\n".join(lines) if lines else "[No features extracted]"


def derive_blank_spec(geo_result: dict) -> str:
    """Derive blank material spec string from geometry analysis result.

    Shape rules (PRT orientation-invariant):
      轴类  -> phi D x L =1   (D = max cylinder diameter; L = longest dim)
      盘类  -> phi D x H =1   (D = max cylinder diameter; H = shortest dim)
      板类  -> delta T x L x W =1 (T = shortest dim = thickness; L>=W)
      other -> L x W x H =1  (sorted descending)

    Returns "" when geo_result is empty or contains an error key.
    """
    if not geo_result or "error" in geo_result:
        return ""

    dims = geo_result.get("dimensions", {})
    x = dims.get("x", 0)
    y = dims.get("y", 0)
    z = dims.get("z", 0)
    if not (x or y or z):
        return ""

    sorted_dims = sorted([x, y, z])  # [min, mid, max]

    faces = geo_result.get("faces", [])
    cylinders = [f for f in faces if f.get("type_name") == "Cylinder"]
    radii = [f.get("params", {}).get("radius", 0) for f in cylinders]
    max_r = max(radii, default=0)

    def _fmt(v: float) -> str:
        return str(int(v)) if v == int(v) else str(round(v, 1))

    shape = geo_result.get("shape_class", "一般件")

    if shape == "轴类" and max_r > 0:
        D = _fmt(round(max_r * 2, 1))
        L = _fmt(sorted_dims[2])
        return f"φ{D}×{L}=1"
    elif shape == "盘类" and max_r > 0:
        D = _fmt(round(max_r * 2, 1))
        H = _fmt(sorted_dims[0])
        return f"φ{D}×{H}=1"
    elif shape == "板类":
        T = _fmt(sorted_dims[0])
        W = _fmt(sorted_dims[1])
        L = _fmt(sorted_dims[2])
        return f"δ{T}×{L}×{W}=1"
    else:
        L = _fmt(sorted_dims[2])
        W = _fmt(sorted_dims[1])
        H = _fmt(sorted_dims[0])
        return f"{L}×{W}×{H}=1"


# Standalone test
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python geometry.py <step_file>")
        sys.exit(1)

    step_file = sys.argv[1]
    print(f"Analyzing: {step_file}")
    print("-" * 40)
    print(extract_features_from_step(step_file))
