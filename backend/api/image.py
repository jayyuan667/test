# -*- coding: utf-8 -*-
"""Image endpoint for serving PNG preview images."""

import os
from flask import Blueprint, send_file

from ..config import OUTPUT_FOLDER

image_bp = Blueprint("image", __name__)


@image_bp.route("/image/<task_id>/<filename>", methods=["GET"])
def get_image(task_id, filename):
    """Serve a PNG image file for preview.

    Args:
        task_id: The task ID
        filename: The image filename (e.g., page_1.png)

    Returns:
        Image file or 404 error
    """
    image_path = os.path.join(OUTPUT_FOLDER, task_id, filename)
    if os.path.exists(image_path):
        return send_file(image_path, mimetype="image/png")
    return "Image not found", 404
