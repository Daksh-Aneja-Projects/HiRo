// Small pure helpers that shape real API responses into recharts [{name,value}] arrays.
// No fabricated data: every helper just reshapes whatever the backend actually returned.

export const objToSeries = (obj = {}) =>
  Object.entries(obj || {}).map(([name, value]) => ({ name, value: Number(value) || 0 }));

// Accepts a bare array, or a wrapped payload like { tickets: [...] } / { items: [...] },
// because different endpoints return different envelopes.
export const toArray = (input) => {
  if (Array.isArray(input)) return input;
  if (!input || typeof input !== 'object') return [];
  const key = Object.keys(input).find((k) => Array.isArray(input[k]));
  return key ? input[key] : [];
};

export const countBy = (arr, keyFn) => {
  const acc = {};
  toArray(arr).forEach((x) => {
    const k = keyFn(x) || 'Unknown';
    acc[k] = (acc[k] || 0) + 1;
  });
  return Object.entries(acc).map(([name, value]) => ({ name, value }));
};

// skillGapSeries and readinessSeries used to live here. The first turned a
// severity label into a bar, and the second was that same label subtracted from
// four, so the two charts on the talent screen were one number and its inverse.
// Both are now computed from real skill coverage and real succession cover in
// the planning service.
