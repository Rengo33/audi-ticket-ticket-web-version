export const PRICE_CATEGORIES = [
  { value: 0, label: 'Kat 3 - Block 237 (120€)' },
  { value: 1, label: 'Kat 1 - Block 136 (200€)' },
  { value: 2, label: 'Kat 1 - Block 328 (200€)' },
]

export const priceCategoryLabel = (idx) => {
  const labels = ['Kat3-237', 'Kat1-136', 'Kat1-328']
  return labels[idx || 0] || `Kat${idx}`
}
