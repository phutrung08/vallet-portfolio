import { inject, type InjectionKey } from 'vue'
import { api } from '@/lib/api'

export type Reader = <T>(path: string, signal?: AbortSignal) => Promise<T>

/** Provides trip read transport and whether mutation UI should be hidden (demo mode). */
export interface TripSource {
  read: Reader
  /** True for bundled demo trips where mutations and invite controls are disabled. */
  readonly: boolean
  /** Base route prefix for trip navigation: `/trips/<id>` or `/demo`. */
  home: (tripId: string) => string
}

export const liveRead: Reader = (path, signal) => api.get(path, { signal })

const live: TripSource = { read: liveRead, readonly: false, home: (tripId) => `/trips/${tripId}` }

export const tripSourceKey: InjectionKey<TripSource> = Symbol('tripSource')

export function useTripSource(): TripSource {
  return inject(tripSourceKey, live)
}
