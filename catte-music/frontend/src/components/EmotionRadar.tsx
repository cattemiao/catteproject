import { useEffect, useRef } from 'react'
import p5 from 'p5'
import type { RadarDimension } from '../types'

interface Props {
  dimensions: RadarDimension
  color: string
  maxSize?: number
  // 主情绪标准模板画像，叠加为虚线轮廓用于对比（默认白色）
  template?: RadarDimension | null
  templateColor?: string
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

export default function EmotionRadar({ dimensions, color, maxSize = 380, template, templateColor = '#ffffff' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const targetValuesRef = useRef(LABELS.map(({ key }) => dimensions[key] ?? 50))
  const templateValuesRef = useRef<number[] | null>(
    template ? LABELS.map(({ key }) => template[key] ?? 50) : null,
  )

  // Update target values when dimensions change
  useEffect(() => {
    targetValuesRef.current = LABELS.map(({ key }) => dimensions[key] ?? 50)
    templateValuesRef.current = template
      ? LABELS.map(({ key }) => template[key] ?? 50)
      : null
  }, [dimensions, template])

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

        const rgba = hexToRgba(color, 1)
        const tc = templateValuesRef.current ? hexToRgba(templateColor, 1) : null
        const ctx = p.drawingContext

        // 背景底光：中心向外主题色渐变光晕（替代纯白网格的平淡感）
        const bgGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, radius)
        bgGrad.addColorStop(0, `rgba(${rgba[0]},${rgba[1]},${rgba[2]},0.13)`)
        bgGrad.addColorStop(1, `rgba(${rgba[0]},${rgba[1]},${rgba[2]},0)`)
        ctx.fillStyle = bgGrad
        ctx.beginPath()
        ctx.arc(0, 0, radius, 0, Math.PI * 2)
        ctx.fill()

        // 背景网格：主题色同心多边形（内亮外暗）+ 径向线，与页面霓虹风格一致
        p.noFill()
        p.strokeWeight(1)
        for (let i = 1; i <= 4; i++) {
          const r = (radius / 4) * i
          p.stroke(rgba[0], rgba[1], rgba[2], 14 + i * 13)
          drawPolygon(p, 0, 0, r, 7)
        }
        for (let i = 0; i < 7; i++) {
          const angle = p.map(i, 0, 7, -p.HALF_PI, p.TWO_PI - p.HALF_PI)
          p.stroke(rgba[0], rgba[1], rgba[2], 15)
          p.line(0, 0, p.cos(angle) * radius, p.sin(angle) * radius)
        }

        // 标签（维度名 + 该情绪模板在此维度的典型值）
        p.textFont('sans-serif')
        p.textAlign(p.CENTER, p.CENTER)
        for (let i = 0; i < LABELS.length; i++) {
          const angle = p.map(i, 0, LABELS.length, -p.HALF_PI, p.TWO_PI - p.HALF_PI)
          const x = p.cos(angle) * (radius + 22)
          const y = p.sin(angle) * (radius + 22)
          p.fill(255, 235)
          p.textSize(12.5)
          p.text(LABELS[i].label, x, y)
        }

        // 动画过渡到目标值
        for (let i = 0; i < currentValues.length; i++) {
          currentValues[i] = p.lerp(currentValues[i], targetValuesRef.current[i], 0.08)
        }

        // 实测画像顶点坐标
        const pts = LABELS.map((_, i) => {
          const angle = p.map(i, 0, LABELS.length, -p.HALF_PI, p.TWO_PI - p.HALF_PI)
          const r = p.map(currentValues[i], 0, 100, 0, radius)
          return [p.cos(angle) * r, p.sin(angle) * r] as [number, number]
        })

        // 填充区域：中心亮 → 边缘透明的主题色径向渐变
        const fillGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, radius)
        fillGrad.addColorStop(0, `rgba(${rgba[0]},${rgba[1]},${rgba[2]},0.42)`)
        fillGrad.addColorStop(1, `rgba(${rgba[0]},${rgba[1]},${rgba[2]},0.06)`)
        ctx.fillStyle = fillGrad
        ctx.beginPath()
        ctx.moveTo(pts[0][0], pts[0][1])
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1])
        ctx.closePath()
        ctx.fill()

        // 外发光描边（霓虹效果）
        ctx.strokeStyle = `rgba(${rgba[0]},${rgba[1]},${rgba[2]},0.9)`
        ctx.lineWidth = 2.5
        ctx.lineJoin = 'round'
        ctx.shadowColor = `rgba(${rgba[0]},${rgba[1]},${rgba[2]},0.55)`
        ctx.shadowBlur = 14
        ctx.beginPath()
        ctx.moveTo(pts[0][0], pts[0][1])
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1])
        ctx.closePath()
        ctx.stroke()
        ctx.shadowBlur = 0

        // 发光节点：外光晕 + 主题色 + 白色芯
        for (let i = 0; i < pts.length; i++) {
          const [x, y] = pts[i]
          p.noStroke()
          p.fill(rgba[0], rgba[1], rgba[2], 55)
          p.circle(x, y, 16)
          p.fill(rgba[0], rgba[1], rgba[2], 235)
          p.circle(x, y, 7)
          p.fill(255, 255, 255, 235)
          p.circle(x, y, 3)
        }

        // 情绪标准模板画像：置于最顶层，白色光晕打底 + 互补色虚线 + 节点
        if (templateValuesRef.current && tc) {
          const tpts = templateValuesRef.current.map((v, i) => {
            const angle = p.map(i, 0, LABELS.length, -p.HALF_PI, p.TWO_PI - p.HALF_PI)
            const r = p.map(v, 0, 100, 0, radius)
            return [p.cos(angle) * r, p.sin(angle) * r] as [number, number]
          })
          // 白色光晕虚线打底，保证在任何背景/覆盖下都清晰可见
          p.push()
          p.drawingContext.setLineDash([7, 5])
          p.noFill()
          p.stroke(255, 255, 255, 80)
          p.strokeWeight(6)
          p.beginShape()
          for (const [x, y] of tpts) p.vertex(x, y)
          p.endShape(p.CLOSE)
          p.drawingContext.setLineDash([])
          p.pop()
          // 主色虚线（互补色）
          p.push()
          p.drawingContext.setLineDash([7, 5])
          p.noFill()
          p.stroke(tc[0], tc[1], tc[2], 255)
          p.strokeWeight(2.5)
          p.beginShape()
          for (const [x, y] of tpts) p.vertex(x, y)
          p.endShape(p.CLOSE)
          p.drawingContext.setLineDash([])
          p.pop()
          // 模板顶点节点（白色描边 + 互补色填充）
          for (const [x, y] of tpts) {
            p.stroke(255, 255, 255, 220)
            p.strokeWeight(2)
            p.fill(tc[0], tc[1], tc[2], 255)
            p.circle(x, y, 9)
          }
        }

        p.pop()
      }

      p.windowResized = () => {
        const newSize = Math.min(container.offsetWidth, maxSize)
        p.resizeCanvas(newSize, newSize)
        cx = newSize / 2
        cy = newSize / 2
        radius = newSize / 2 - 50
      }
    }

    const p5Instance = new p5(sketch, container)
    return () => p5Instance.remove()
  }, [dimensions, color, maxSize])

  return <div ref={containerRef} className="mx-auto" style={{ width: maxSize, maxWidth: '100%' }} />
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