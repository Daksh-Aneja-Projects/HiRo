// BrainParticles - the knowledge core as a dense particle sphere (Canvas 2D).
// Points are hash-scattered in a disc (never angle-proportional-to-index,
// which draws visible spiral arms). Warm coral with red accents against the
// cool UI. Renders one static frame under prefers-reduced-motion.
import React, { memo, useEffect, useRef } from 'react';

const CORAL = '#fb923c';
const RED = '#ef4444';

// Deterministic hash in [0, 1) so the sphere is stable across renders.
const hash = (i, salt) => {
    let h = (i + 1) * 2654435761 + salt * 40503;
    h = (h ^ (h >> 13)) * 1274126177;
    return ((h ^ (h >> 16)) >>> 0) / 4294967296;
};

const BrainParticles = memo(({ size = 300, density = 1, reduced: reducedProp }) => {
    const canvasRef = useRef(null);
    const rafRef = useRef(0);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return undefined;
        const dpr = window.devicePixelRatio || 1;
        canvas.width = size * dpr;
        canvas.height = size * dpr;
        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);

        const R = size * 0.44;
        const cx = size / 2;
        const cy = size / 2;
        const count = Math.round(size * 0.6 * Math.min(1.4, Math.max(0.35, density)));
        const linkDist = R * 0.34;

        const pts = Array.from({ length: count }, (_, i) => {
            const r = R * Math.sqrt(hash(i, 1)) * 0.96;
            const ang = hash(i, 2) * Math.PI * 2;
            return {
                x: cx + Math.cos(ang) * r,
                y: cy + Math.sin(ang) * r,
                vx: (hash(i, 3) - 0.5) * 0.3,
                vy: (hash(i, 4) - 0.5) * 0.3,
                accent: hash(i, 5) < 0.1,
            };
        });

        const draw = () => {
            ctx.clearRect(0, 0, size, size);
            // Links between close neighbors, alpha faded by distance.
            for (let i = 0; i < pts.length; i++) {
                for (let j = i + 1; j < pts.length; j++) {
                    const dx = pts[i].x - pts[j].x;
                    const dy = pts[i].y - pts[j].y;
                    const d = Math.hypot(dx, dy);
                    if (d < linkDist) {
                        ctx.strokeStyle = `rgba(251,146,60,${0.16 * (1 - d / linkDist)})`;
                        ctx.lineWidth = 0.6;
                        ctx.beginPath();
                        ctx.moveTo(pts[i].x, pts[i].y);
                        ctx.lineTo(pts[j].x, pts[j].y);
                        ctx.stroke();
                    }
                }
            }
            pts.forEach((p) => {
                ctx.fillStyle = p.accent ? RED : CORAL;
                ctx.globalAlpha = p.accent ? 0.95 : 0.65;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.accent ? 2.1 : 1.2, 0, Math.PI * 2);
                ctx.fill();
            });
            ctx.globalAlpha = 1;
        };

        const step = () => {
            pts.forEach((p) => {
                // A whisper of noise so the cloud never drifts coherently
                // into a clump, plus a speed cap so it stays a slow swirl.
                p.vx += (Math.random() - 0.5) * 0.02;
                p.vy += (Math.random() - 0.5) * 0.02;
                const sp = Math.hypot(p.vx, p.vy);
                if (sp > 0.35) { p.vx *= 0.35 / sp; p.vy *= 0.35 / sp; }
                p.x += p.vx;
                p.y += p.vy;
                // Soft spherical boundary: nudge back past 88% of the radius.
                const dx = p.x - cx;
                const dy = p.y - cy;
                const d = Math.hypot(dx, dy);
                if (d > R * 0.88) {
                    p.vx -= (dx / d) * 0.03;
                    p.vy -= (dy / d) * 0.03;
                }
            });
            draw();
            rafRef.current = requestAnimationFrame(step);
        };

        // The page owns the motion decision (see useMotionPreference); the
        // media query is only the fallback when no preference is passed down.
        const reduced = reducedProp !== undefined
            ? reducedProp
            : (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
        if (reduced) {
            draw();
            return undefined;
        }
        rafRef.current = requestAnimationFrame(step);
        return () => cancelAnimationFrame(rafRef.current);
    }, [size, density, reducedProp]);

    return (
        <canvas
            ref={canvasRef}
            style={{ width: size, height: size, display: 'block' }}
            aria-label="Knowledge core particle sphere"
            role="img"
        />
    );
});

BrainParticles.displayName = 'BrainParticles';
export default BrainParticles;
