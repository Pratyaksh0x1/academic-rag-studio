import { useEffect, useRef, useState } from 'react'
import { FileText, Layers3, Quote, Sparkles } from 'lucide-react'

/**
 * PaperHero
 * ---------
 * Intro banner for the top of the app: a research-paper mockup gets
 * "scanned" by a moving cyan line, and as the line passes it spins off
 * small data chips (chunk / embedding / citation) that drift toward the
 * graph panel below — a literal dramatization of ingest -> index -> retrieve.
 *
 * No animation libraries required (project has none installed); everything
 * here is plain CSS keyframes + one IntersectionObserver-driven class toggle.
 * Respects prefers-reduced-motion.
 */

const CHIPS = [
  { icon: Layers3, label: 'chunking', top: '22%' },
  { icon: Sparkles, label: 'embedding', top: '48%' },
  { icon: Quote, label: 'citation', top: '74%' },
]

export function PaperHero({ paperSrc = '/research-paper.png' }: { paperSrc?: string }) {
  const [entered, setEntered] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    // Trigger the load-in sequence once, shortly after mount, rather than
    // on scroll — this sits at the very top of the page.
    const t = window.setTimeout(() => setEntered(true), 120)
    return () => window.clearTimeout(t)
  }, [])

  return (
    <div className={`paper-hero ${entered ? 'is-in' : ''}`} ref={rootRef}>
      <div className="paper-hero-copy">
        <span className="tiny-label">
          <FileText size={13} /> DOCUMENT INGEST
        </span>
        <h1>
          Every paper you upload becomes <span className="accent">structured, citable knowledge</span>.
        </h1>
        <p>
          PDFs are parsed, chunked, embedded, and indexed automatically — so the assistant answers
          from your library instead of guessing.
        </p>
      </div>

      <div className="paper-hero-stage">
        <div className="paper-hero-frame">
          <img src={paperSrc} alt="Research paper being indexed" className="paper-hero-image" />
          <div className="paper-hero-scanline" aria-hidden="true" />
          <div className="paper-hero-vignette" aria-hidden="true" />

          {CHIPS.map(({ icon: Icon, label, top }, i) => (
            <div
              key={label}
              className="paper-hero-chip"
              style={{ top, animationDelay: `${0.9 + i * 0.6}s` }}
            >
              <Icon size={12} />
              {label}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
