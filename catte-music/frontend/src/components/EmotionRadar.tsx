import { useEffect, useRef } from 'react'
import p5 from 'p5'
import type { RadarDimension } from '../types'

interface Props {
  dimensions: RadarDimension
  color: string
}

const LABELS: { key: keyof RadarDimension; label: string }[] = [
  { key: 'loudness', label: '响度' },
  { key: 'high_freq', label: '高频' },
  { key: 'rhythm', label: '节奏' },
  { key: 'soundstage', label: '声场' },
  { key: 'layering', label: '层次' },
  { key: 'soothing', label: '舒缓' },
  { key: 'prosody', label: '韵律' },
]

export default function EmotionRadar({ dimensions, color }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const targetValuesRef = useRef(LABELS.map(({ key }) => dimensions[key] ?? 50))

  // Update target values when dimensions change
  useEffect(() => {
    targetValuesRef.current = LABELS.map(({ key }) => dimensions[key] ?? 50)
  }, [dimensions])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const size = Math.min(container.offsetWidth, 380)
    let cx = size / 2
    let cy = size / 2
    let radius = size / 2 - 50
    let currentValues = LABELS.map(() => 0)

    const sketch = (p: p5) => {
      p.setup = () => {
        p.createCanvas(size, size)
        p.frameRate(30)
      }

      p.draw = () => {
        p.clear()
        p.push()
        p.translate(cx, cy)

        // 背景网格
        p.stroke(255, 15)
        p.strokeWeight(1)
        for (let i = 1; i <= 4; i++) {
          const r = (radius / 4) * i
          drawPolygon(p, 0, 0, r, 7)
        }
        for (let i = 0; i < 7; i++) {
          const angle = p.map(i, 0, 7, -p.HALF_PI, p.TWO_PI - p.HALF_PI)
          p.line(0, 0, p.cos(angle) * radius, p.sin(angle) * radius)
        }

        // 标签
        p.fill(255, 180)
        p.textFont('sans-serif')
        p.textSize(12)
        p.textAlign(p.CENTER, p.CENTER)
        for (let i = 0; i < LABELS.length; i++) {
          const angle = p.map(i, 0, LABELS.length, -p.HALF_PI, p.TWO_PI - p.HALF_PI)
          const x = p.cos(angle) * (radius + 22)
          const y = p.sin(angle) * (radius + 22)
          p.text(LABELS[i].label, x, y)
        }

        // 动画过渡到目标值
        for (let i = 0; i < currentValues.length; i++) {
          currentValues[i] = p.lerp(currentValues[i], targetValuesRef.current[i], 0.08)
        }

        // 绘制填充区域
        p.beginShape()
        for (let i = 0; i < LABELS.length; i++) {
          const angle = p.map(i, 0, LABELS.length, -p.HALF_PI, p.TWO_PI - p.HALF_PI)
          const r = p.map(currentValues[i], 0, 100, 0, radius)
          p.vertex(p.cos(angle) * r, p.sin(angle) * r)
        }
        p.endShape(p.CLOSE)
        const rgba = hexToRgba(color, 0.3)
        p.fill(rgba[0], rgba[1], rgba[2], 80)
        p.noStroke()

        // 绘制外发光描边
        p.beginShape()
        for (let i = 0; i < LABELS.length; i++) {
          const angle = p.map(i, 0, LABELS.length, -p.HALF_PI, p.TWO_PI - p.HALF_PI)
          const r = p.map(currentValues[i], 0, 100, 0, radius)
          p.vertex(p.cos(angle) * r, p.sin(angle) * r)
        }
        p.endShape(p.CLOSE)
        const rgba2 = hexToRgba(color, 0.7)
        p.stroke(rgba2[0], rgba2[1], rgba2[2], 200)
        p.strokeWeight(2.5)
        p.noFill()

        // 发光节点
        for (let i = 0; i < LABELS.length; i++) {
          const angle = p.map(i, 0, LABELS.length, -p.HALF_PI, p.TWO_PI - p.HALF_PI)
          const r = p.map(currentValues[i], 0, 100, 0, radius)
          p.fill(rgba2[0], rgba2[1], rgba2[2], 220)
          p.noStroke()
          p.circle(p.cos(angle) * r, p.sin(angle) * r, 6)
          // 外发光
          p.fill(rgba2[0], rgba2[1], rgba2[2], 60)
          p.circle(p.cos(angle) * r, p.sin(angle) * r, 14)
        }

        p.pop()
      }

      p.windowResized = () => {
        const newSize = Math.min(container.offsetWidth, 380)
        p.resizeCanvas(newSize, newSize)
        cx = newSize / 2
        cy = newSize / 2
        radius = newSize / 2 - 50
      }
    }

    const p5Instance = new p5(sketch, container)
    return () => p5Instance.remove()
  }, [dimensions, color])

  return <div ref={containerRef} className="mx-auto" style={{ width: 380, maxWidth: '100%' }} />
}

function hexToRgba(hex: string, _: number): [number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return [r, g, b]
}

function drawPolygon(p: p5, x: number, y: number, radius: number, sides: number) {
  p.beginShape()
  for (let i = 0; i < sides; i++) {
    const angle = p.map(i, 0, sides, -p.HALF_PI, p.TWO_PI - p.HALF_PI)
    p.vertex(x + p.cos(angle) * radius, y + p.sin(angle) * radius)
  }
  p.endShape(p.CLOSE)
}