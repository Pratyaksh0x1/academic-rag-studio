import { useEffect, useRef } from 'react'
import * as THREE from 'three'

interface Scene3DProps {
  active: boolean
  nodeCount: number
}

export function Scene3D({ active, nodeCount }: Scene3DProps) {
  const mountRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return undefined

    const scene = new THREE.Scene()
    scene.fog = new THREE.Fog('#101820', 8, 24)
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100)
    camera.position.set(0, 2.2, 8.6)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setClearColor(0x000000, 0)
    mount.appendChild(renderer.domElement)

    const group = new THREE.Group()
    scene.add(group)
    const geometry = new THREE.IcosahedronGeometry(0.1, 1)
    const nodes = Math.max(22, Math.min(70, nodeCount * 5 || 28))
    const materials = [
      new THREE.MeshBasicMaterial({ color: '#7bdff2' }),
      new THREE.MeshBasicMaterial({ color: '#f2b134' }),
      new THREE.MeshBasicMaterial({ color: '#ed6a5a' }),
    ]

    for (let i = 0; i < nodes; i += 1) {
      const node = new THREE.Mesh(geometry, materials[i % materials.length])
      const angle = (i / nodes) * Math.PI * 2
      const radius = 1.1 + (i % 5) * 0.28
      node.position.set(Math.cos(angle) * radius, Math.sin(angle * 1.7) * 1.1, Math.sin(angle) * radius)
      group.add(node)
    }

    const lineMaterial = new THREE.LineBasicMaterial({ color: '#315160', transparent: true, opacity: 0.5 })
    const linePositions: number[] = []
    for (let i = 0; i < nodes - 1; i += 1) {
      const from = group.children[i].position
      const to = group.children[i + 1].position
      linePositions.push(from.x, from.y, from.z, to.x, to.y, to.z)
    }
    const lines = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3)), lineMaterial)
    group.add(lines)

    const pointer = { x: 0, y: 0 }
    const onPointerMove = (event: PointerEvent) => {
      const rect = mount.getBoundingClientRect()
      pointer.x = ((event.clientX - rect.left) / rect.width - 0.5) * 0.35
      pointer.y = ((event.clientY - rect.top) / rect.height - 0.5) * 0.18
    }
    mount.addEventListener('pointermove', onPointerMove)

    const resize = () => {
      const width = mount.clientWidth || 1
      const height = mount.clientHeight || 1
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
    }
    resize()
    const observer = new ResizeObserver(resize)
    observer.observe(mount)

    let frame = 0
    const animate = () => {
      frame = requestAnimationFrame(animate)
      group.rotation.y += active ? 0.0028 : 0.0008
      group.rotation.x += (pointer.y - group.rotation.x) * 0.018
      group.rotation.z += (pointer.x - group.rotation.z) * 0.018
      renderer.render(scene, camera)
    }
    animate()

    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      mount.removeEventListener('pointermove', onPointerMove)
      renderer.dispose()
      geometry.dispose()
      materials.forEach((material) => material.dispose())
      lineMaterial.dispose()
      lines.geometry.dispose()
      mount.removeChild(renderer.domElement)
    }
  }, [active, nodeCount])

  return <div className="scene-wrap" ref={mountRef} aria-label="Interactive 3D research graph" />
}
