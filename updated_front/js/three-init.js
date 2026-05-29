import * as _THREE from 'three';
import { GLTFLoader } from './GLTFLoader.js';
// Module namespaces are frozen; spread into a plain object so GLTFLoader can be attached
window.THREE = Object.assign(Object.create(null), _THREE, { GLTFLoader });
