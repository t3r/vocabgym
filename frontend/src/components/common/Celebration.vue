<template>
  <div
    v-if="active"
    class="fixed inset-0 z-50 pointer-events-none"
    aria-hidden="true"
  >
    <!-- Canvas confetti / fireworks -->
    <canvas ref="canvas" class="w-full h-full block"></canvas>

    <!-- Reduced-motion fallback: a brief static emoji, no animation -->
    <div
      v-if="reducedMotion && staticVisible"
      class="absolute inset-0 flex items-center justify-center"
    >
      <span class="text-6xl select-none">{{ intensity === 'big' ? '🎆' : '🎉' }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, nextTick } from 'vue'

/**
 * Self-contained celebration animation (no external dependency).
 * - intensity 'small' → a single confetti burst.
 * - intensity 'big'   → several firework bursts, more particles, longer.
 * Respects prefers-reduced-motion: shows a brief static emoji instead of motion.
 *
 * Usage: obtain a ref and call celebrate('small' | 'big').
 */

const active = ref(false)
const canvas = ref(null)
const intensity = ref('small')
const reducedMotion = ref(false)
const staticVisible = ref(false)

let rafId = null
let particles = []
let ctx = null
let startTime = 0
let durationMs = 0
let staticTimer = null

const COLORS = ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899', '#eab308']

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function rand(min, max) {
  return min + Math.random() * (max - min)
}

/** Spawn a burst of particles emanating from (x, y). */
function spawnBurst(x, y, count, power) {
  for (let i = 0; i < count; i++) {
    const angle = rand(0, Math.PI * 2)
    const speed = rand(power * 0.3, power)
    particles.push({
      x,
      y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      size: rand(3, 7),
      color: COLORS[(Math.random() * COLORS.length) | 0],
      rotation: rand(0, Math.PI * 2),
      vrot: rand(-0.2, 0.2),
      life: 1,
    })
  }
}

function seedParticles(w, h) {
  particles = []
  if (intensity.value === 'big') {
    // Several firework bursts at different positions/times feel are approximated
    // by spawning multiple bursts up-front across the upper half.
    const bursts = 6
    for (let b = 0; b < bursts; b++) {
      spawnBurst(rand(w * 0.15, w * 0.85), rand(h * 0.15, h * 0.5), 120, rand(6, 11))
    }
  } else {
    // Small: one confetti burst from the top-center.
    spawnBurst(w / 2, h * 0.28, 90, 8)
  }
}

function tick(now) {
  if (!ctx || !canvas.value) return
  const w = canvas.value.width
  const h = canvas.value.height
  const elapsed = now - startTime
  const gravity = 0.15

  ctx.clearRect(0, 0, w, h)

  for (const p of particles) {
    p.vy += gravity
    p.x += p.vx
    p.y += p.vy
    p.rotation += p.vrot
    p.life = Math.max(0, 1 - elapsed / durationMs)

    ctx.save()
    ctx.globalAlpha = p.life
    ctx.translate(p.x, p.y)
    ctx.rotate(p.rotation)
    ctx.fillStyle = p.color
    ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size)
    ctx.restore()
  }

  if (elapsed < durationMs) {
    rafId = requestAnimationFrame(tick)
  } else {
    stop()
  }
}

function stop() {
  if (rafId) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
  if (staticTimer) {
    clearTimeout(staticTimer)
    staticTimer = null
  }
  particles = []
  active.value = false
  staticVisible.value = false
}

/**
 * Trigger a celebration.
 * @param {'small'|'big'} level
 */
async function celebrate(level = 'small') {
  intensity.value = level === 'big' ? 'big' : 'small'
  reducedMotion.value = prefersReducedMotion()
  active.value = true

  // Reduced motion: show a brief static emoji, no canvas animation.
  if (reducedMotion.value) {
    staticVisible.value = true
    staticTimer = setTimeout(stop, 1200)
    return
  }

  durationMs = intensity.value === 'big' ? 3500 : 1800

  await nextTick()
  const el = canvas.value
  if (!el) return
  // Size the canvas to the viewport (device-pixel aware for crispness).
  const dpr = window.devicePixelRatio || 1
  el.width = window.innerWidth * dpr
  el.height = window.innerHeight * dpr
  ctx = el.getContext('2d')
  if (ctx && dpr !== 1) ctx.scale(1, 1) // particles already in device px space

  seedParticles(el.width, el.height)
  startTime = performance.now()
  rafId = requestAnimationFrame(tick)
}

onBeforeUnmount(stop)

defineExpose({ celebrate })
</script>
