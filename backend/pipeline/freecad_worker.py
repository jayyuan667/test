#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Standalone FreeCAD subprocess worker.

Runs in its own process so Qt/FreeCAD GUI objects are always created on the
main thread — eliminates QObject::setParent cross-thread warnings and ensures
clean document state for every call.

Usage (called by prt_pipeline._run_freecad_worker):
    python freecad_worker.py capture_views  <step_file> <output_dir>
    python freecad_worker.py export_gltf    <step_file> <output_dir>

Environment:
    FREECAD_PATHS_JSON  JSON array of paths to prepend to sys.path
    QT_QPA_PLATFORM_PLUGIN_PATH / QT_PLUGIN_PATH  set by parent if needed
"""
import json
import os
import sys
import time

# ------------------------------------------------------------------
# Bootstrap: add FreeCAD paths from parent process
# ------------------------------------------------------------------
_fc_paths: list[str] = []
try:
    _fc_paths = json.loads(os.environ.get("FREECAD_PATHS_JSON", "[]"))
except Exception:
    pass

for _p in _fc_paths:
    if _p and os.path.exists(_p) and _p not in sys.path:
        sys.path.append(_p)


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

def capture_views(step_file: str, output_dir: str) -> bool:
    import FreeCAD as App
    import FreeCADGui as Gui
    import Part

    abs_step = os.path.abspath(step_file)
    abs_out = os.path.abspath(output_dir)
    os.makedirs(abs_out, exist_ok=True)

    if hasattr(Gui, "setupGui"):
        Gui.setupGui()
    else:
        Gui.showMainWindow()

    prefs = App.ParamGet("User parameter:BaseApp/Preferences/View")
    orig_anim = prefs.GetBool("EnableAnimation", True)
    prefs.SetBool("EnableAnimation", False)

    doc = App.newDocument("BatchDoc")
    doc_name = doc.Name
    try:
        shape = Part.read(abs_step)
        obj = doc.addObject("Part::Feature", "Model")
        obj.Shape = shape
        doc.recompute()

        Gui.setActiveDocument(doc)
        view = Gui.activeDocument().ActiveView
        if not view:
            Gui.activeDocument().createView("Gui::View3DInventor")
            view = Gui.activeDocument().ActiveView

        view.setCameraType("Orthographic")

        for label, cmd in [("front", "viewFront"), ("top", "viewTop"), ("right", "viewRight")]:
            getattr(view, cmd)()
            view.fitAll()
            for _ in range(10):
                Gui.updateGui()
                time.sleep(0.05)
            out_path = os.path.join(abs_out, f"{label}.png")
            for bg in ("White", None, "Current"):
                try:
                    view.saveImage(out_path, 1920, 1440, bg)
                    break
                except Exception:
                    pass
            print(f"Generated: {out_path}", flush=True)

        return True
    except Exception as e:
        print(f"[worker] capture_views error: {e}", file=sys.stderr, flush=True)
        return False
    finally:
        prefs.SetBool("EnableAnimation", orig_anim)
        try:
            App.closeDocument(doc_name)
        except Exception:
            pass


def export_gltf(step_file: str, output_dir: str) -> str:
    import FreeCAD as App
    import FreeCADGui as Gui  # required: triggers tessellation engine for mesh export
    import Part
    import Import

    abs_step = os.path.abspath(step_file)
    os.makedirs(output_dir, exist_ok=True)

    if hasattr(Gui, "setupGui"):
        Gui.setupGui()
    else:
        Gui.showMainWindow()

    doc = App.newDocument("GltfDoc")
    doc_name = doc.Name
    try:
        shape = Part.read(abs_step)
        obj = doc.addObject("Part::Feature", "Model")
        obj.Shape = shape
        doc.recompute()
        gltf_path = os.path.join(output_dir, "model.glb")
        Import.export([obj], gltf_path)
        size = os.path.getsize(gltf_path) if os.path.exists(gltf_path) else 0
        print(f"GLTF_PATH:{gltf_path}", flush=True)
        print(f"[worker] glb size: {size} bytes", flush=True)
        return gltf_path
    except Exception as e:
        print(f"[worker] export_gltf error: {e}", file=sys.stderr, flush=True)
        raise
    finally:
        try:
            App.closeDocument(doc_name)
        except Exception:
            pass


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <capture_views|export_gltf> <step_file> <output_dir>",
              file=sys.stderr)
        sys.exit(1)

    cmd, step_file, output_dir = sys.argv[1], sys.argv[2], sys.argv[3]

    if cmd == "capture_views":
        ok = capture_views(step_file, output_dir)
        sys.exit(0 if ok else 1)
    elif cmd == "export_gltf":
        try:
            export_gltf(step_file, output_dir)
            sys.exit(0)
        except Exception:
            sys.exit(1)
    else:
        print(f"[worker] Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
