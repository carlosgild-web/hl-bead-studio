import { Bounds, Center, Environment, Lightformer, OrbitControls, useGLTF } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Suspense, useMemo } from 'react'
import * as THREE from 'three'

import type { Kind, Swatch } from '@/api/types'

/** Borosilicate glass (manual 07-colors-and-finishes); the Blender presets use the same IOR. */
const GLASS_IOR = 1.47

function material(kind: Kind, swatch: Swatch | undefined): THREE.Material {
  const color = new THREE.Color(swatch?.hex ?? '#c9d2e0')
  if (kind === 'charm') {
    // A fully metallic surface shows only reflections, and the local light formers alone
    // leave it nearly black; a little diffuse keeps the plating color readable.
    return new THREE.MeshPhysicalMaterial({
      color,
      metalness: Math.min(swatch?.metallic ?? 1, 0.65),
      roughness: Math.max(swatch?.roughness ?? 0.2, 0.3),
      clearcoat: 0.6,
      clearcoatRoughness: 0.15,
    })
  }
  const transmission = swatch?.transmission ?? 0.8
  return new THREE.MeshPhysicalMaterial({
    color,
    roughness: 0.06,
    transmission,
    thickness: 3,
    ior: GLASS_IOR,
    clearcoat: 1,
    clearcoatRoughness: 0.05,
    attenuationColor: color,
    attenuationDistance: 6,
  })
}

function Model({ url, kind, swatch }: { url: string; kind: Kind; swatch?: Swatch }) {
  const { scene } = useGLTF(url)
  const look = useMemo(() => material(kind, swatch), [kind, swatch])
  const object = useMemo(() => {
    const copy = scene.clone(true)
    copy.traverse((child) => {
      if (child instanceof THREE.Mesh) child.material = look
    })
    return copy
  }, [scene, look])
  return (
    <Center>
      {/* CadQuery models are Z-up; three.js is Y-up. */}
      <primitive object={object} rotation={[-Math.PI / 2, 0, 0]} />
    </Center>
  )
}

/**
 * The GLB the backend built from the validated parameters (millimetres), with the chosen
 * glass color or plating finish. Lights are local (no environment map download).
 */
export function BeadPreview({
  url,
  kind,
  swatch,
  label,
}: {
  url: string
  kind: Kind
  swatch?: Swatch
  label: string
}) {
  return (
    <div className="size-full" role="img" aria-label={label}>
      <Canvas camera={{ position: [0, 6, 30], fov: 35 }} dpr={[1, 2]}>
        <color attach="background" args={['#f3f0ea']} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 20, 10]} intensity={1.6} />
        <directionalLight position={[-12, 5, -8]} intensity={0.6} />
        <Environment resolution={128}>
          <Lightformer form="rect" intensity={3} position={[0, 6, 6]} scale={[12, 4, 1]} />
          <Lightformer form="rect" intensity={1.5} position={[-8, 2, -4]} scale={[6, 6, 1]} />
          <Lightformer form="ring" intensity={2} position={[8, 4, 2]} scale={3} />
        </Environment>
        <Suspense fallback={null}>
          <Bounds fit clip observe margin={1.4}>
            <Model url={url} kind={kind} swatch={swatch} />
          </Bounds>
        </Suspense>
        <OrbitControls makeDefault enablePan={false} />
      </Canvas>
    </div>
  )
}
