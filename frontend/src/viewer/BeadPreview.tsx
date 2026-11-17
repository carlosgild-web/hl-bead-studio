import { OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'

/**
 * Placeholder 3D viewer: a glass-like torus standing in for a bead. Phase 6 replaces it
 * with the GLB that `preview_geometry` builds from the validated parameters (units: mm).
 */
export function BeadPreview({ label }: { label: string }) {
  return (
    <div className="h-80 w-full overflow-hidden rounded-lg border bg-muted" aria-label={label}>
      <Canvas camera={{ position: [0, 0, 30], fov: 40 }}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[10, 15, 10]} intensity={1.2} />
        {/* A 10 mm bead with a 2 mm hole: torus radius 3, tube radius 2 (mm). */}
        <mesh rotation={[Math.PI / 2.5, 0, 0]}>
          <torusGeometry args={[3, 2, 48, 96]} />
          <meshPhysicalMaterial
            color="#c9822b"
            roughness={0.1}
            transmission={0.6}
            thickness={2}
            ior={1.47}
          />
        </mesh>
        <OrbitControls enablePan={false} />
      </Canvas>
    </div>
  )
}
