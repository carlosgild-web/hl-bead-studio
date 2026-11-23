/**
 * The GLB is already Y-up (`glb_bytes` turns CadQuery's Z-up −90° about X), so the viewer
 * undoes that turn: the CadQuery XY plane faces the camera, a charm's loop (+Y) points up and
 * its front face (+Z) looks at the viewer. Rotating −90° again flipped charms upside down.
 * Beads are symmetric about their hole axis, so they look the same either way.
 */
export const MODEL_ROTATION: [number, number, number] = [Math.PI / 2, 0, 0]
