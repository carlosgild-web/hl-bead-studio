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
    // Plating is fully metallic, as in the Blender presets: its color comes only from what it
    // reflects. Mixing in diffuse (metalness below 1) under neutral light turned gold olive;
    // the studio below gives the metal a bright, warm surround to reflect instead.
    return new THREE.MeshPhysicalMaterial({
      color,
      metalness: swatch?.metallic ?? 1,
      roughness: Math.min(Math.max(swatch?.roughness ?? 0.2, 0.12), 0.35),
      envMapIntensity: 1.4,
      clearcoat: 0.4,
      clearcoatRoughness: 0.1,
    })
  }
  // Transmission shows what is behind the bead: the backdrop light former in the studio.
  // A thin optical path and a long attenuation keep the color clear instead of muddy.
  const transmission = swatch?.transmission ?? 0.8
  return new THREE.MeshPhysicalMaterial({
    color,
    roughness: 0.04,
    transmission,
    thickness: 1.2,
    ior: GLASS_IOR,
    clearcoat: 1,
    clearcoatRoughness: 0.03,
    attenuationColor: color,
    attenuationDistance: 7,
    envMapIntensity: 1.2,
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
        <Environment resolution={256}>
          {/* A photo studio: key softbox, warm side light, a large backdrop that the glass
              transmits and the metal reflects, and a ring for highlights. The warm grey
              surround fills every other direction: a flat metal face (an initial charm seen
              from the front) reflects one direction only, and without it that was black. */}
          <color attach="background" args={['#9c958c']} />
          <Lightformer form="rect" intensity={3} position={[0, 6, 6]} scale={[12, 4, 1]} />
          <Lightformer form="rect" intensity={1.6} color="#ffe2b8" position={[-8, 2, -4]} scale={[6, 6, 1]} />
          <Lightformer form="rect" intensity={1.2} color="#f6f1e8" position={[0, 0, -12]} scale={[40, 24, 1]} />
          <Lightformer form="ring" intensity={2} position={[8, 4, 2]} scale={3} />
          {/* The reflector behind the camera, facing the model: a flat metal face seen from
              the front mirrors exactly this direction, so without it the face was black. */}
          <Lightformer
            form="rect"
            intensity={1.4}
            color="#fff4e2"
            position={[0, 2, 22]}
            rotation={[0, Math.PI, 0]}
            scale={[36, 22, 1]}
          />
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
