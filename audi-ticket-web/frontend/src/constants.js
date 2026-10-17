export const PRICE_CATEGORIES = [
  { value: 0, label: 'Kat 3 - Block 237 (120€)' },
  { value: 1, label: 'Kat 1 - Block 136 (200€)' },
  { value: 2, label: 'Kat 1 - Block 328 (200€)' },
]

export const priceCategoryLabel = (idx) => {
  const labels = ['Kat3-237', 'Kat1-136', 'Kat1-328']
  return labels[idx || 0] || `Kat${idx}`
}

// When the bot starts polling on the sale day. Mirror of backend
// audi-ticket-web/backend/app/api/games.py (hour=5, minute=55, Europe/Berlin).
// Audi's published "sale time" is meaningless — drops happen randomly on the
// sale day — so the UI shows when WE fire instead.
export const SCHEDULE_FIRE_TIME = '05:55'
