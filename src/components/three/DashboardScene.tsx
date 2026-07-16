'use client'

import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

function stableUnit(seed: number) {
  const value = Math.sin(seed * 12.9898) * 43758.5453
  return value - Math.floor(value)
}

// 浮动几何体 — 工业感网格球体
function FloatingGeo({ position, scale = 1, speed = 1 }: { position: [number, number, number]; scale?: number; speed?: number }) {
  const meshRef = useRef<THREE.Mesh>(null!)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() * speed
    meshRef.current.rotation.x = t * 0.3
    meshRef.current.rotation.y = t * 0.2
    meshRef.current.position.y = position[1] + Math.sin(t * 0.8) * 0.15
  })

  return (
    <mesh ref={meshRef} position={position} scale={scale}>
      <icosahedronGeometry args={[1, 1]} />
      <meshStandardMaterial
        color="#e07828"
        wireframe
        transparent
        opacity={0.15}
        emissive="#e07828"
        emissiveIntensity={0.1}
      />
    </mesh>
  )
}

// 网格地面
function GridFloor() {
  return (
    <gridHelper
      args={[20, 20, '#e07828', '#e07828']}
      position={[0, -2, 0]}
      rotation={[0, 0, 0]}
    />
  )
}

// 粒子场
function ParticleField() {
  const count = 80
  const meshRef = useRef<THREE.InstancedMesh>(null!)

  const dummy = useMemo(() => new THREE.Object3D(), [])
  const particles = useMemo(() =>
    Array.from({ length: count }, (_, index) => ({
      x: (stableUnit(index * 5 + 1) - 0.5) * 8,
      y: (stableUnit(index * 5 + 2) - 0.5) * 4,
      z: (stableUnit(index * 5 + 3) - 0.5) * 4 - 2,
      speed: stableUnit(index * 5 + 4) * 0.5 + 0.2,
      offset: stableUnit(index * 5 + 5) * Math.PI * 2,
    })), []
  )

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    particles.forEach((p, i) => {
      dummy.position.set(
        p.x + Math.sin(t * p.speed + p.offset) * 0.3,
        p.y + Math.cos(t * p.speed * 0.7 + p.offset) * 0.2,
        p.z
      )
      dummy.scale.setScalar(0.02 + Math.sin(t * p.speed + p.offset) * 0.01)
      dummy.updateMatrix()
      meshRef.current.setMatrixAt(i, dummy.matrix)
    })
    meshRef.current.instanceMatrix.needsUpdate = true
  })

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
      <sphereGeometry args={[1, 6, 6]} />
      <meshBasicMaterial color="#e07828" transparent opacity={0.4} />
    </instancedMesh>
  )
}

// 场景内容
function SceneContent() {
  return (
    <>
      <ambientLight intensity={0.3} />
      <directionalLight position={[5, 5, 5]} intensity={0.5} color="#e07828" />
      <pointLight position={[-3, 2, 4]} intensity={0.3} color="#e07828" />

      <FloatingGeo position={[-2.5, 0.5, -1]} scale={0.6} speed={0.8} />
      <FloatingGeo position={[2.5, -0.3, -1.5]} scale={0.4} speed={1.2} />
      <FloatingGeo position={[0, 1, -2]} scale={0.35} speed={0.6} />

      <GridFloor />
      <ParticleField />
    </>
  )
}

// 导出组件
export function DashboardScene() {
  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
      zIndex: 0, pointerEvents: 'none', opacity: 0.6,
    }}>
      <Canvas
        camera={{ position: [0, 0, 5], fov: 50 }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: 'transparent' }}
      >
        <SceneContent />
      </Canvas>
    </div>
  )
}
