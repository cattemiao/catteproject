---
title: www.cattemiao.com 访问体验评估（2026-08-16）
type: Note
date: 2026-08-16
tags: [性能评估, 移动端, Vite, 前端优化]
---

# www.cattemiao.com 访问体验评估（2026-08-16）

## 结论

www.cattemiao.com 当前线上跑的是 Vite 开发服务器（未构建的生产包），叠加美国主机 + 极低的服务器吞吐，移动端首屏 30 秒~数分钟是常态，几乎无法使用。

## 实测证据

| 项 | 实测值 | 判定 |
|---|---|---|
| 首页 HTML | 返回 `/@vite/client`、`/@react-refresh`、`/src/main.tsx` 源码 | ❌ 开发模式暴露在生产 |
| 模块请求数 | 26 个同源模块（无打包） | ❌ 生产应有 1-2 个 bundle |
| 总下载量 | 4.87 MB（未压缩源码 + 未压缩 vendor） | ❌ 正常应在 1 MB 内 |
| 串行累计加载 | 238.7 秒（平均每请求 9.2s） | ❌ 灾难级 |
| p5.js 热缓存二次请求 | 1.45 MB 花了 52.9 秒（≈27 KB/s） | ❌ 服务器吞吐极低 |
| logo.png | 577 KB，26.8 秒 | ❌ 图片未优化 |
| HTTP 协议 | HTTP/1.1（ALPN 不支持 h2） | ❌ 无多路复用 |
| TLS 握手 | 1.5 秒 | ❌ 服务器处理慢 |
| 服务器位置 | 104.168.22.113（美国 ColoCrossing） | ⚠️ 对国内用户 RTT 200ms+ |
| 证书 | Let's Encrypt ECDSA，有效 | ✅ |
| 渲染阻塞 | `<link>` Google Fonts 样式表 | ❌ 国内被墙，等待超时 |

## 手机端为什么"非常慢"（按影响排序）

1. **生产环境跑 dev server**（根因）。Vite 开发服务器按需即时编译 TSX、不经打包/压缩，26 个模块 = 26 次独立请求，每个都消耗 RTT + 服务器 CPU。正常 `vite build` 后应是一个压缩 bundle。
2. **服务器吞吐 ~25 KB/s**。热缓存模块仍要几十秒传输——nginx 代理到 dev server 的链路或出口带宽极差，1.45 MB 的 p5.js 就要 53 秒。
3. **HTTP/1.1 + 美国主机**。无多路复用，移动端每域名最多 6 并发；国内手机到美国 ~200-400ms RTT 被放大到每个模块请求上。
4. **Google Fonts 渲染阻塞**。国内网络无法访问 fonts.googleapis.com，样式表卡住 → 白屏期等于浏览器超时时间。
5. **资源超肥**：p5.js 1.45MB、lucide-react 1.07MB、906KB chunk 全为未压缩 dev 产物，加 577KB logo。

估算移动端白屏时间：5 波请求 × 平均 9s+ ≈ 45 秒起步，弱网下数分钟。

## 修复优先级

1. `npm run build` 并在 nginx 上托管 `dist/`（立竿见影：26 请求→2-3 个，体积 4.9MB→<1MB）
2. 换国内 CDN/服务器（或至少上 Cloudflare 免费版，顺带解决 Google Fonts 可用性）
3. 启用 HTTP/2
4. Google Fonts 改自托管（`display=swap` 已设，但 link 本身仍阻塞）；或移除
5. logo.png 压缩到 <100KB，MusicKit 按需懒加载
6. 排查吞吐：nginx → dev server 代理限速或服务器带宽上限

## 局限

本机不在中国大陆网络，Google Fonts 被墙为普遍事实推断；服务器吞吐为单连接测量，多连接下总带宽可能略高，但单请求 27KB/s 已是硬伤。
