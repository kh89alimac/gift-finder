// ── Price formatting ───────────────────────────────────────────────────────
export function formatPrice(amount: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount);
}

// ── Date formatting ────────────────────────────────────────────────────────
export function formatRelativeDate(date: string | Date | null | undefined): string {
  if (!date) return 'Unknown';
  const now = new Date();
  const d = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(d.getTime())) return 'Unknown';
  const diffMs = now.getTime() - d.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  const diffWeeks = Math.floor(diffDays / 7);
  const diffMonths = Math.floor(diffDays / 30);
  const diffYears = Math.floor(diffDays / 365);

  if (diffSecs < 60) return 'just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
  if (diffWeeks < 4) return `${diffWeeks} week${diffWeeks !== 1 ? 's' : ''} ago`;
  if (diffMonths < 12) return `${diffMonths} month${diffMonths !== 1 ? 's' : ''} ago`;
  return `${diffYears} year${diffYears !== 1 ? 's' : ''} ago`;
}

export function formatAbsoluteDate(date: string | Date | null | undefined): string {
  if (!date) return 'Unknown';
  const d = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(d.getTime())) return 'Unknown';
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d);
}

export function formatDate(date: string | Date | null | undefined): { relative: string; absolute: string } {
  return {
    relative: formatRelativeDate(date),
    absolute: formatAbsoluteDate(date),
  };
}

// ── String utilities ───────────────────────────────────────────────────────
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 3) + '…';
}

// ── URL safety ─────────────────────────────────────────────────────────────
// Defence-in-depth against `javascript:` / `data:` URLs leaking into
// <a href>. The backend already filters these on write, but we double-check
// at render-time so a stale row can never produce a clickable XSS vector.
export function safeUrl(url: string | null | undefined): string {
  if (!url) return '#';
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return '#';
    return url;
  } catch {
    return '#';
  }
}

// ── Cron expression parser ─────────────────────────────────────────────────
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const DAYS_OF_WEEK = [
  'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
];

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

function formatTime(hour: string, minute: string): string {
  const h = parseInt(hour, 10);
  const m = parseInt(minute, 10);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const displayHour = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${displayHour}:${pad(m)} ${ampm}`;
}

export function parseCronToHuman(expr: string): string {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return expr;

  const [minute, hour, dom, month, dow] = parts;

  const everyMinute = minute === '*';
  const everyHour = hour === '*';
  const everyDom = dom === '*';
  const everyMonth = month === '*';
  const everyDow = dow === '*';

  // Every minute
  if (everyMinute && everyHour && everyDom && everyMonth && everyDow) {
    return 'Every minute';
  }

  // Every N minutes
  if (minute.startsWith('*/') && everyHour && everyDom && everyMonth && everyDow) {
    const n = minute.slice(2);
    return `Every ${n} minutes`;
  }

  // Every hour at :MM
  if (everyHour && everyDom && everyMonth && everyDow && !everyMinute) {
    return `Every hour at :${pad(parseInt(minute, 10))}`;
  }

  // Every N hours
  if (hour.startsWith('*/') && everyDom && everyMonth && everyDow) {
    const n = hour.slice(2);
    const m = everyMinute ? '00' : pad(parseInt(minute, 10));
    return `Every ${n} hours at :${m}`;
  }

  // Daily at HH:MM
  if (!everyHour && everyDom && everyMonth && everyDow) {
    // Could be a list of hours like "0,12"
    if (hour.includes(',')) {
      const hours = hour.split(',').map((h) => formatTime(h, minute)).join(' and ');
      return `Daily at ${hours}`;
    }
    return `Every day at ${formatTime(hour, minute)}`;
  }

  // Weekly (specific dow)
  if (!everyDow && everyDom && everyMonth) {
    const dayName = DAYS_OF_WEEK[parseInt(dow, 10)] ?? dow;
    const time = everyHour ? 'every hour' : `at ${formatTime(hour, minute)}`;
    return `Every ${dayName} ${time}`;
  }

  // Monthly (specific day of month)
  if (!everyDom && everyMonth && everyDow) {
    const suffix = getOrdinalSuffix(parseInt(dom, 10));
    const time = everyHour ? '' : ` at ${formatTime(hour, minute)}`;
    return `Monthly on the ${dom}${suffix}${time}`;
  }

  // Yearly
  if (!everyDom && !everyMonth && everyDow) {
    const monthName = MONTHS[parseInt(month, 10) - 1] ?? month;
    const time = everyHour ? '' : ` at ${formatTime(hour, minute)}`;
    return `Yearly on ${monthName} ${dom}${time}`;
  }

  // Weekdays
  if (dow === '1-5' && everyDom) {
    return `Weekdays at ${formatTime(hour, minute)}`;
  }

  // Weekends
  if (dow === '0,6' && everyDom) {
    return `Weekends at ${formatTime(hour, minute)}`;
  }

  return expr;
}

function getOrdinalSuffix(n: number): string {
  if (n >= 11 && n <= 13) return 'th';
  switch (n % 10) {
    case 1: return 'st';
    case 2: return 'nd';
    case 3: return 'rd';
    default: return 'th';
  }
}
