import { useEffect, useRef } from 'react'
import p5 from 'p5'

interface ParticleBgProps {
  /** 情绪主色调 */
  color?: string
  /** 粒子数量，移动端自动降低 */
  count?: number
}

/**
 * p5.js 情绪粒子背景组件。
 * 粒子随情绪主色调变色与流动，带拖尾与辉光效果。
 */
export default function ParticleBg({ color = '#a855f7', count }: ParticleBgProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const colorRef = useRef(color)
  colorRef.current = color

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const isMobile = window.innerWidth < 768
    const particleCount = count ?? (isMobile ? 60 : 150)

    const sketch = (p: p5) => {
      let particles: Array<{
        x: number
        y: number
        vx: number
        vy: number
        size: number
      }> = []

      p.setup = () => {
        const canvas = p.createCanvas(container.offsetWidth, container.offsetHeight)
        canvas.parent(container)
        initParticles()
      }

      const initParticles = () => {
        particles = []
        for (let i = 0; i < particleCount; i++) {
          particles.push({
            x: p.random(p.width),
            y: p.random(p.height),
            vx: p.random(-0.5, 0.5),
            vy: p.random(-0.5, 0.5),
            size: p.random(1.5, 4),
          })
        }
      }

      p.draw = () => {
        // 半透明背景制造拖尾效果
        p.background(10, 10, 18, 25)

        const c = p.color(colorRef.current)
        c.setAlpha(180)

        for (const particle of particles) {
          particle.x += particle.vx
          particle.y += particle.vy

          // 边界回弹
          if (particle.x < 0 || particle.x > p.width) particle.vx *= -1
          if (particle.y < 0 || particle.y > p.height) particle.vy *= -1

          // 辉光
          p.noStroke()
          p.drawingContext.shadowBlur = 15
          p.drawingContext.shadowColor = colorRef.current
          p.fill(c)
          p.circle(particle.x, particle.y, particle.size)
        }
        p.drawingContext.shadowBlur = 0
      }

      p.windowResized = () => {
        p.resizeCanvas(container.offsetWidth, container.offsetHeight)
      }
    }

    const instance = new p5(sketch)
    return () => instance.remove()
  }, [count])

  return <div ref={containerRef} className="absolute inset-0 -z-10" />
}
