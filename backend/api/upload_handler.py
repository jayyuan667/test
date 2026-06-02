# -*- coding: utf-8 -*-
"""Task creation and file reception."""

import os, uuid, threading, logging
from datetime import datetime
from flask import Blueprint, request, jsonify

from ..config import UPLOAD_FOLDER, OUTPUT_FOLDER
from ..prt_pipeline import prepare_prt_artifacts, export_gltf, extract_geometry_features
from ..task_store import insert_task
from ._utils import extract_prefix_from_filename

upload_bp = Blueprint("upload", __name__)
logger = logging.getLogger(__name__)

tasks = {}
event_data = {}
event_locks = {}


def set_shared_state(tasks_dict, event_data_dict, event_locks_dict):
    global tasks, event_data, event_locks
    tasks = tasks_dict
    event_data = event_data_dict
    event_locks = event_locks_dict


_extract_prefix_from_filename = extract_prefix_from_filename
