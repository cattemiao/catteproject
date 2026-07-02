import { useEffect, useRef } from 'react'
import p5 from 'p5'

interface EmotionRadarProps {
  dimensions: {
    loudness: number
    high_freq: number
    vocal: number
    rhythm: number
    soundstage: number
    space: number
    layering: number
  }
  color?: string
}

const LABELS = ['响度', '高频', '人声', '节奏', '声场', '空间', '层次']
const KEYS: Array<keyof EmotionRadarProps['dimensions']> = [
  'loudness', 'high_freq', 'vocal', 'rhythm', 'soundstage', 'space', 'layering',
]

/**
 * 情绪雷达图：霓虹描边 + 渐变填充 + 发光节点。
 */
export default function EmotionRadar({ dimensions, color = '#a855f7' }: EmotionRadarProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const dataRef = useRef(dimensions)
  dataRef.current = dimensions
  const colorRef = useRef(color)
  colorRef.current = color

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const sketch = (p: p5) => {
      const size = Math.min(container.offsetWidth, 360)
      let cx: number, cy: number, radius: number
      let animProgress = 0

      p.setup = () => {
        const canvas = p.createCanvas(container.offsetWidth, size)
        canvas.parent(container)
        cx = p.width / 2
        cy = size / 2
        radius = size / 2 - 40
      }

      p.draw = () => {
        p.clear()
        animProgress = Math.min(animProgress + 0.03, 1)

        const data = dataRef.current
        const c = p.color(colorRef.current)
        const n = 7

        // 网格圈
        p.noFill()
        p.stroke(255, 30)
        p.strokeWeight(1)
        for (let r = 1; r <= 4; r++) {
          p.beginShape()
          for (let i = 0; i <= n; i++) {
            const angle = (p.TWO_PI * i) / n - p.HALF_PI
            const rr = (radius * r) / 4
            p.vertex(cx + p.cos(angle) * rr, cy + p.sin(angle) * rr)
          }
          p.endShape()
        }

        // 数据多边形（渐变填充 + 霓虹描边）
        c.setAlpha(60)
        p.fill(c)
        p.stroke(colorRef.current)
        p.strokeWeight(2)
        p.drawingContext.shadowBlur = 20
        p.drawingContext.shadowColor = colorRef.current

        p.beginShape()
        const values = KEYS.map((k) => data[k])
        for (let i = 0; i < n; i++) {
          const angle = (p.TWO_PI * i) / n - p.HALF_PI
          const val = (values[i] / 100) * animProgress
          const rx = cx + p.cos(angle) * radius * val
          const ry = cy + p.sin(angle) * radius * val
          p.vertex(rx, ry)
        }
        p.endShape(p.CLOSE)

        // 发光节点
        p.drawingContext.shadowBlur = 12
        p.noStroke()
        p.fill(255)
        for (let i = 0; i < n; i++) {
          const angle = (p.TWO_PI * i) / n - p.HALF_PI
          const val = (values[i] / 100) * animProgress
          const rx = cx + p.cos(angle) * radius * val
          const ry = cy + p.sin(angle) * radius * val
          p.circle(rx, ry, 6)
        }
        p.drawingContext.shadowBlur = 0

        // 标签
        p.fill(200)
        p.noStroke()
        p.textAlign(p.CENTER, p.CENTER)
        p.textSize(11)
        for (let i = 0; i < n; i++) {
          const angle = (p.TWO_PI * i) / n - p.HALF_PI
          const lx = cx + p.cos(angle) * (radius + 20)
          const ly = cy + p.sin(angle) * (radius + 20)
          p.text(LABELS[i], lx, ly)
        }
      }

      p.windowResized = () => {
        const newSize = Math.min(container.offsetWidth, 360)
        p.resizeContainer(container.offsetWidth, newSize)
        cx = p.width / 2
        cy = newSize / 2
        radius = newSize / 2 - 40
      }
    }

    const instance = new p5(sketch)
    return () => instance.remove()
  }, [])

  return <div ref={containerRef} className="w-full max-w-sm mx-auto" />
}
