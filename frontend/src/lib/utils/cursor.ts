interface CursorData {
  publishedAt: string;
  id: string;
}

export function encodeCursor(publishedAt: string, id: string): string {
  const raw = JSON.stringify({ publishedAt, id });
  if (typeof window !== 'undefined') {
    return btoa(raw);
  }
  return Buffer.from(raw).toString('base64');
}

export function decodeCursor(cursor: string): CursorData {
  try {
    let raw: string;
    if (typeof window !== 'undefined') {
      raw = atob(cursor);
    } else {
      raw = Buffer.from(cursor, 'base64').toString('utf8');
    }
    return JSON.parse(raw) as CursorData;
  } catch {
    throw new Error(`Invalid cursor: ${cursor}`);
  }
}
