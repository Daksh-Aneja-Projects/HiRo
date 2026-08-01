// useCountUp - eases a displayed integer toward its target (cubic-out) so
// live counts transition instead of hard-swapping. First mount counts up from
// zero. Under prefers-reduced-motion the value snaps.
import { useEffect, useRef, useState } from 'react';

export default function useCountUp(target, duration = 800) {
    const [value, setValue] = useState(0);
    const fromRef = useRef(0);

    useEffect(() => {
        const to = Number(target) || 0;
        const from = fromRef.current;
        if (from === to) return undefined;
        const reduced = typeof window !== 'undefined'
            && window.matchMedia
            && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (reduced) {
            fromRef.current = to;
            setValue(to);
            return undefined;
        }
        const t0 = performance.now();
        let raf;
        const step = (t) => {
            const p = Math.min(1, (t - t0) / duration);
            const e = 1 - Math.pow(1 - p, 3);
            const v = from + (to - from) * e;
            setValue(v);
            if (p < 1) {
                raf = requestAnimationFrame(step);
            } else {
                fromRef.current = to;
            }
        };
        raf = requestAnimationFrame(step);
        return () => cancelAnimationFrame(raf);
    }, [target, duration]);

    return Math.round(value);
}
