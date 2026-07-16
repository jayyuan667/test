'use client'

import { useRef, useEffect, useCallback } from 'react'
import * as THREE from 'three'

/**
 * Lusion 风格流体光标效果 — WebGL 版
 * 用 Three.js + GLSL 着色器实现 GPU 加速流体模拟
 * 核心：速度场 FBO + 平流 + 模糊 + 衰减
 */

interface FluidCursorWebGLProps {
  theme: 'dark' | 'light'
}

// 顶点着色器
const vertexShader = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 1.0);
}
`

// 流体模拟着色器（Splat + Advection + Decay）
const fluidShader = `
precision highp float;
uniform sampler2D uVelocity;
uniform vec2 uMouse;
uniform vec2 uPrevMouse;
uniform vec2 uResolution;
uniform float uTime;
uniform float uDecay;
uniform float uRadius;
uniform float uStrength;
uniform float uAspect;
varying vec2 vUv;

void main() {
  vec2 uv = vUv;
  vec2 texel = 1.0 / uResolution;

  // 当前速度
  vec2 vel = texture2D(uVelocity, uv).xy;

  // 鼠标 Splat
  vec2 mouseUV = uMouse;
  vec2 prevMouseUV = uPrevMouse;
  vec2 mouseVel = (mouseUV - prevMouseUV) * 50.0;

  vec2 aspect = vec2(uAspect, 1.0);
  vec2 dx = (uv - mouseUV) * aspect;
  float dist = length(dx);
  float splat = exp(-dist / uRadius);
  vel += mouseVel * uStrength * splat;

  // 平流（Advection）
  vec2 advectUV = uv - vel * 0.004;
  vec2 advected = texture2D(uVelocity, advectUV).xy;

  // 混合 + 衰减
  vel = mix(vel, advected, 0.9) * exp(-uDecay);

  gl_FragColor = vec4(vel, 0.0, 1.0);
}
`

// 渲染着色器（彩虹色散 + 流体可视化）
const renderShader = `
precision highp float;
uniform sampler2D uVelocity;
uniform float uIntensity;
uniform float uTime;
varying vec2 vUv;

// HSV 转 RGB
vec3 hsv2rgb(vec3 c) {
  vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
  vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
  return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
  vec2 vel = texture2D(uVelocity, vUv).xy;
  float speed = length(vel);

  // 发光效果
  float glow = speed * uIntensity;
  glow = clamp(glow, 0.0, 0.6);

  // 彩虹色：根据速度方向映射色相
  float hue = fract(atan(vel.y, vel.x) / 6.283 + 0.5);
  // 根据速度大小调整饱和度和亮度
  float sat = 0.7 + speed * 0.3;
  float val = 0.8 + speed * 0.2;
  vec3 rainbow = hsv2rgb(vec3(hue, sat, val));

  // 混合：彩虹色 + 橙色基调
  vec3 baseColor = vec3(0.88, 0.47, 0.16); // 橙色
  vec3 color = mix(baseColor, rainbow, 0.6) * glow;

  // 边缘渐变
  float edge = smoothstep(0.0, 0.05, speed);

  // 透明度：中心更亮，边缘渐隐
  float alpha = glow * edge * 0.8;

  gl_FragColor = vec4(color, alpha);
}
`

export function FluidCursorWebGL({ theme }: FluidCursorWebGLProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  const setup = useCallback(() => {
    const container = containerRef.current
    if (!container) return

    // 场景设置
    const scene = new THREE.Scene()
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)
    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: false,
      powerPreference: 'high-performance',
    })

    // 全屏渲染
    renderer.setSize(window.innerWidth, window.innerHeight)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    container.appendChild(renderer.domElement)
    renderer.domElement.style.width = '100%'
    renderer.domElement.style.height = '100%'
    renderer.domElement.style.pointerEvents = 'none'
    renderer.domElement.style.position = 'absolute'
    renderer.domElement.style.top = '0'
    renderer.domElement.style.left = '0'

    // 流体模拟用较小分辨率（性能）
    const simSize = 256

    // 渲染目标（双缓冲）- 流体模拟用小分辨率
    const rtA = new THREE.WebGLRenderTarget(simSize, simSize, {
      type: THREE.FloatType,
      format: THREE.RGBAFormat,
    })
    const rtB = new THREE.WebGLRenderTarget(simSize, simSize, {
      type: THREE.FloatType,
      format: THREE.RGBAFormat,
    })
    let currentRT = rtA
    let prevRT = rtB

    // 流体模拟材质
    const fluidMaterial = new THREE.ShaderMaterial({
      uniforms: {
        uVelocity: { value: null },
        uMouse: { value: new THREE.Vector2(-1, -1) },
        uPrevMouse: { value: new THREE.Vector2(-1, -1) },
        uResolution: { value: new THREE.Vector2(simSize, simSize) },
        uTime: { value: 0 },
        uDecay: { value: 0.02 },
        uRadius: { value: 0.03 },
        uStrength: { value: 1.5 },
        uAspect: { value: window.innerWidth / window.innerHeight },
      },
      vertexShader,
      fragmentShader: fluidShader,
    })

    // 渲染材质
    const renderMaterial = new THREE.ShaderMaterial({
      uniforms: {
        uVelocity: { value: null },
        uIntensity: { value: theme === 'dark' ? 2.5 : 1.8 },
        uTime: { value: 0 },
      },
      vertexShader,
      fragmentShader: renderShader,
      transparent: true,
      blending: THREE.AdditiveBlending,
    })

    // 全屏四边形
    const geometry = new THREE.PlaneGeometry(2, 2)
    const fluidMesh = new THREE.Mesh(geometry, fluidMaterial)
    const renderMesh = new THREE.Mesh(geometry, renderMaterial)
    scene.add(fluidMesh)

    // 鼠标状态（屏幕像素坐标）
    let mouseX = -100
    let mouseY = -100
    let prevMouseX = -100
    let prevMouseY = -100
    let isActive = false

    const onMouseMove = (e: MouseEvent) => {
      mouseX = e.clientX
      mouseY = e.clientY
      isActive = true
    }

    const onMouseLeave = () => { isActive = false }

    // 窗口大小变化
    const onResize = () => {
      renderer.setSize(window.innerWidth, window.innerHeight)
      fluidMaterial.uniforms.uAspect.value = window.innerWidth / window.innerHeight
    }
    window.addEventListener('resize', onResize)

    // 动画循环
    let previousTime = performance.now()
    const animate = () => {
      requestAnimationFrame(animate)

      const now = performance.now()
      const dt = Math.min((now - previousTime) / 1000, 0.05)
      previousTime = now
      fluidMaterial.uniforms.uTime.value += dt
      fluidMaterial.uniforms.uAspect.value = window.innerWidth / window.innerHeight

      // 转换为 UV 坐标 (0-1)
      const uvX = mouseX / window.innerWidth
      const uvY = 1.0 - mouseY / window.innerHeight
      const prevUvX = prevMouseX / window.innerWidth
      const prevUvY = 1.0 - prevMouseY / window.innerHeight

      if (isActive) {
        fluidMaterial.uniforms.uMouse.value.set(uvX, uvY)
        fluidMaterial.uniforms.uPrevMouse.value.set(prevUvX, prevUvY)
      } else {
        fluidMaterial.uniforms.uMouse.value.set(-1, -1)
      }

      // 流体模拟 pass
      fluidMaterial.uniforms.uVelocity.value = prevRT.texture
      renderer.setRenderTarget(currentRT)
      renderer.render(fluidMesh, camera)

      // 渲染到屏幕
      renderMaterial.uniforms.uVelocity.value = currentRT.texture
      renderMaterial.uniforms.uTime.value = fluidMaterial.uniforms.uTime.value
      renderer.setRenderTarget(null)
      renderer.render(renderMesh, camera)

      // 交换缓冲
      const temp = currentRT
      currentRT = prevRT
      prevRT = temp

      prevMouseX = mouseX
      prevMouseY = mouseY
    }

    animate()

    window.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseleave', onMouseLeave)

    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('resize', onResize)
      document.removeEventListener('mouseleave', onMouseLeave)
      renderer.dispose()
      rtA.dispose()
      rtB.dispose()
      container.removeChild(renderer.domElement)
    }
  }, [theme])

  useEffect(() => setup(), [setup])

  return (
    <div ref={containerRef} style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100%',
      height: '100%',
      zIndex: 50,
      pointerEvents: 'none',
      opacity: 0.8,
    }} />
  )
}
