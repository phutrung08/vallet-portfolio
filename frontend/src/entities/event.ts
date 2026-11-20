export interface TripEvent {
  id: string
  kind: string
  actor_id: string | null
  subject_id: string | null
  created_at: string
}

export interface EventPage {
  events: TripEvent[]
  next_before: string | null
}
