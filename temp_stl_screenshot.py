"""FreeCAD: import STL, export 3-view screenshots."""
import os, sys

stl_path = r"C:\Users\86152\xwechat_files\wxid_og0kf2j8t2ka22_d410\temp\RWTemp\2026-05\f3a05093664e48c5b4d3f3a29fea48bd\转子.stl"
out_dir = r"F:\Work_Dir\new_3dversion\my_working\temp_stl_views"
os.makedirs(out_dir, exist_ok=True)

import FreeCAD, FreeCADGui, Mesh, Part

doc = FreeCAD.newDocument("Rotor")
mesh = Mesh.Mesh(stl_path)
mesh_obj = doc.addObject("Mesh::Feature", "Rotor")
mesh_obj.Mesh = mesh

shape = Part.Shape()
shape.makeShapeFromMesh(mesh.Topology, 0.01)
shape_obj = doc.addObject("Part::Feature", "RotorShape")
shape_obj.Shape = shape
doc.recompute()

gdoc = FreeCADGui.getDocument(doc.Name)
view = gdoc.ActiveView
view.viewAxonometric()
FreeCADGui.SendMsgToActiveView("ViewFit")
FreeCADGui.updateGui()

# Front
view.viewFront()
FreeCADGui.updateGui()
view.saveImage(os.path.join(out_dir, "01_front.png"), 1920, 1080, "White")
print("Front saved")

# Top
view.viewTop()
FreeCADGui.updateGui()
view.saveImage(os.path.join(out_dir, "02_top.png"), 1920, 1080, "White")
print("Top saved")

# Right
view.viewRight()
FreeCADGui.updateGui()
view.saveImage(os.path.join(out_dir, "03_right.png"), 1920, 1080, "White")
print("Right saved")

print("Done")
