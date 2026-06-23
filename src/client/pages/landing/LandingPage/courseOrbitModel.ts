import { courses } from './courseData'
import type { CourseCardStyle, CourseFocusCardStyle, CourseOrbitItem, ViewportSize } from './types'
import { clamp, getSignedAngleDistance, lerp, normalizeAngle, smoothstep } from './utils'

export const COURSE_ORBIT_DRAG_SENSITIVITY = 0.18
export const COURSE_ORBIT_WHEEL_SENSITIVITY = 0.12
export const COURSE_ORBIT_INERTIA_FRICTION = 0.94
export const COURSE_ORBIT_MIN_VELOCITY = 0.018
export const COURSE_ORBIT_AUTOPLAY_DELAY_MS = 3000
export const COURSE_ORBIT_AUTOPLAY_SPEED = -0.0028

const COURSE_ORBIT_COPY_COUNT = 5

export const courseOrbitItems: CourseOrbitItem[] = Array.from({ length: COURSE_ORBIT_COPY_COUNT }).flatMap(
  (_, copyIndex) => courses.map((course, courseIndex) => ({
    ...course,
    copyIndex,
    courseIndex,
    orbitIndex: copyIndex * courses.length + courseIndex,
  })),
)
export const COURSE_ORBIT_ANGLE_STEP = 360 / courseOrbitItems.length

type OrbitPose = {
  x: number
  y: number
  z: number
  scale: number
  opacity: number
  brightness: number
  rotateY: number
  rotateZ: number
  signed: number
}

export const getCourseOrbitAngle = (item: CourseOrbitItem, phase: number) => (
  normalizeAngle(item.orbitIndex * COURSE_ORBIT_ANGLE_STEP + phase)
)

export const getOrbitPose = (item: CourseOrbitItem, phase: number, viewportSize: ViewportSize): OrbitPose => {
  const angle = getCourseOrbitAngle(item, phase)
  const signed = getSignedAngleDistance(angle)
  const frontness = clamp(1 - Math.abs(signed) / 180, 0, 1)
  const radians = angle * Math.PI / 180
  const radiusX = clamp(viewportSize.width * 0.31, 240, 560)
  const radiusY = clamp(viewportSize.height * 0.095, 34, 82)
  const radiusZ = clamp(viewportSize.width * 0.54, 460, 900)

  return {
    x: Math.sin(radians) * radiusX,
    y: Math.sin(radians * 2) * radiusY - frontness * 18,
    z: Math.cos(radians) * radiusZ,
    scale: 0.55 + frontness * 0.42,
    opacity: clamp(0.06 + (frontness ** 1.7) * 0.58, 0.06, 0.64),
    brightness: clamp(0.38 + frontness * 0.5, 0.38, 0.88),
    rotateY: Math.sin(radians) * -58,
    rotateZ: signed * 0.18,
    signed,
  }
}

export const getActiveCourseOrbitItem = (phase: number) => (
  courseOrbitItems.reduce((closest, item) => (
    Math.abs(getSignedAngleDistance(getCourseOrbitAngle(item, phase))) <
    Math.abs(getSignedAngleDistance(getCourseOrbitAngle(closest, phase))) ? item : closest
  ), courseOrbitItems[0])
)

const signedIndexDistance = (left: number, right: number) => (
  ((left - right + courseOrbitItems.length * 1.5) % courseOrbitItems.length) - courseOrbitItems.length / 2
)

export const getCourseCardStyle = (
  item: CourseOrbitItem,
  phase: number,
  activeItem: CourseOrbitItem,
  focusStrength: number,
  viewportSize: ViewportSize,
): CourseCardStyle => {
  const pose = getOrbitPose(item, phase, viewportSize)
  const isActive = item.orbitIndex === activeItem.orbitIndex
  const frontCorridor = 0.22 + 0.78 * smoothstep(COURSE_ORBIT_ANGLE_STEP * 2.2, COURSE_ORBIT_ANGLE_STEP * 5.2, Math.abs(pose.signed))
  const neighborCorridor = 0.18 + 0.82 * smoothstep(1.4, 4.8, Math.abs(signedIndexDistance(item.orbitIndex, activeItem.orbitIndex)))
  const corridorFade = isActive ? 1 : lerp(1, Math.min(frontCorridor, neighborCorridor), focusStrength)
  const activeFade = isActive ? 1 - focusStrength * 0.96 : 1
  const opacity = pose.opacity * activeFade * corridorFade
  const brightness = pose.brightness + (isActive ? focusStrength * 0.12 : 0) - (!isActive ? (1 - corridorFade) * 0.1 : 0)

  return {
    '--course-accent': item.accent,
    '--orbit-x': `${pose.x}px`,
    '--orbit-y': `${pose.y}px`,
    '--orbit-z': `${pose.z}px`,
    '--orbit-scale': `${pose.scale}`,
    '--orbit-opacity': `${opacity}`,
    '--orbit-brightness': `${brightness}`,
    '--orbit-rotate-y': `${pose.rotateY}deg`,
    '--orbit-tilt': `${pose.rotateZ}deg`,
    '--orbit-pointer': 'none',
    zIndex: Math.round(1000 + pose.z),
  }
}

export const getFocusCardStyle = (
  activeItem: CourseOrbitItem,
  phase: number,
  focusStrength: number,
  viewportSize: ViewportSize,
): CourseFocusCardStyle => {
  const pose = getOrbitPose(activeItem, phase, viewportSize)
  const targetX = viewportSize.width < 760 ? 0 : clamp(viewportSize.width * 0.018, 12, 32)
  const targetY = viewportSize.width < 760 ? 24 : 38
  const fromX = pose.x * 0.68 - viewportSize.width * 0.04
  const fromY = pose.y * 0.72 - viewportSize.height * 0.04
  const fromZ = Math.min(0, pose.z - clamp(viewportSize.width * 0.42, 320, 620))
  const grip = smoothstep(0.04, 0.72, focusStrength)

  return {
    '--course-accent': activeItem.accent,
    '--focus-x': `${lerp(fromX, targetX, focusStrength)}px`,
    '--focus-y': `${lerp(fromY, targetY, focusStrength)}px`,
    '--focus-z': `${lerp(fromZ, 0, focusStrength)}px`,
    '--focus-scale': `${lerp(pose.scale, viewportSize.width < 760 ? 1 : 1.03, focusStrength)}`,
    '--focus-opacity': `${grip}`,
    '--focus-brightness': `${lerp(pose.brightness, 1.05, focusStrength)}`,
    '--focus-rotate-y': `${lerp(pose.rotateY + 18, 0, focusStrength)}deg`,
    '--focus-rotate-z': `${lerp(pose.rotateZ + 6, 0, focusStrength)}deg`,
  }
}
