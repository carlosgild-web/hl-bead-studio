import * as THREE from 'three'
import { describe, expect, it } from 'vitest'

import { MODEL_ROTATION } from './orientation'

/** What the backend does in `glb_bytes`: CadQuery Z-up turned −90° about X. */
const GLB_EXPORT = new THREE.Matrix4().makeRotationX(-Math.PI / 2)
const VIEWER = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(...MODEL_ROTATION))

function shown(x: number, y: number, z: number): THREE.Vector3 {
  return new THREE.Vector3(x, y, z).applyMatrix4(GLB_EXPORT).applyMatrix4(VIEWER)
}

describe('viewer orientation', () => {
  it('shows a charm loop (CadQuery +Y) pointing up', () => {
    const up = shown(0, 1, 0)
    expect(up.y).toBeCloseTo(1)
    expect(up.x).toBeCloseTo(0)
    expect(up.z).toBeCloseTo(0)
  })

  it('shows the front face (CadQuery +Z) towards the camera', () => {
    expect(shown(0, 0, 1).z).toBeCloseTo(1)
  })

  it('keeps left and right, so a letter is not mirrored', () => {
    expect(shown(1, 0, 0).x).toBeCloseTo(1)
  })
})
