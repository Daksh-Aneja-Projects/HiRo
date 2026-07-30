// Small pure helpers that shape real API responses into recharts [{name,value}] arrays.
// No fabricated data: every helper just reshapes whatever the backend actually returned.

export const objToSeries = (obj = {}) =>
  Object.entries(obj || {}).map(([name, value]) => ({ name, value: Number(value) || 0 }));

export const countBy = (arr = [], keyFn) => {
  const acc = {};
  (arr || []).forEach((x) => {
    const k = keyFn(x) || 'Unknown';
    acc[k] = (acc[k] || 0) + 1;
  });
  return Object.entries(acc).map(([name, value]) => ({ name, value }));
};

const GAP_LEVEL = { HIGH: 3, MEDIUM: 2, LOW: 1 };

// Skill-gap severity as a numeric bar (HIGH gap = 3, LOW gap = 1).
export const skillGapSeries = (gaps = {}) =>
  Object.entries(gaps || {}).map(([name, level]) => ({ name, value: GAP_LEVEL[String(level).toUpperCase()] ?? 0 }));

// Succession readiness = inverse of the gap (LOW gap = high readiness).
export const readinessSeries = (gaps = {}) =>
  Object.entries(gaps || {}).map(([name, level]) => ({ name, value: 4 - (GAP_LEVEL[String(level).toUpperCase()] ?? 0) }));
