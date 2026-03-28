import type { DiscoveryResult } from "@/hooks/use-discover"

const DB_NAME = "gamesight"
const STORE_NAME = "discover_cache"
const DB_VERSION = 1

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "key" })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function buildKey(gameName: string, period: string, dateFrom?: string, dateTo?: string): string {
  return [gameName.toLowerCase().trim(), period, dateFrom ?? "", dateTo ?? ""].join("|")
}

export async function getCachedResult(
  gameName: string,
  period: string,
  dateFrom?: string,
  dateTo?: string,
): Promise<DiscoveryResult | null> {
  try {
    const db = await openDB()
    const key = buildKey(gameName, period, dateFrom, dateTo)
    return new Promise((resolve) => {
      const tx = db.transaction(STORE_NAME, "readonly")
      const req = tx.objectStore(STORE_NAME).get(key)
      req.onsuccess = () => resolve(req.result?.data ?? null)
      req.onerror = () => resolve(null)
    })
  } catch {
    return null
  }
}

export async function setCachedResult(
  gameName: string,
  period: string,
  dateFrom: string | undefined,
  dateTo: string | undefined,
  data: DiscoveryResult,
): Promise<void> {
  try {
    const db = await openDB()
    const key = buildKey(gameName, period, dateFrom, dateTo)
    const tx = db.transaction(STORE_NAME, "readwrite")
    tx.objectStore(STORE_NAME).put({ key, data, cachedAt: Date.now() })
  } catch {
    // silently ignore cache write failures
  }
}
