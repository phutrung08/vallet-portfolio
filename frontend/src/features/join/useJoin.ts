import { getCurrentScope, onScopeDispose, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { JoinPreview, JoinRequest, TripDetail } from '@/entities'
import { extractToken } from '@/features/join/joinToken'
import { checkMemberName } from '@/features/members/memberRules'
import { ApiError, api } from '@/lib/api'

export type JoinPhase = 'paste' | 'loading' | 'ready' | 'gone' | 'failed'

/**
 * Invite join flow. Reads the share token from the URL hash fragment, removes it immediately
 * from history so it never leaks in referrers or server logs, and stores it only in closure memory.
 */
export function useJoin() {
  const router = useRouter()
  const route = useRoute()
  const phase = ref<JoinPhase>('paste')
  const preview = ref<JoinPreview>()
  const failure = ref<unknown>(null)
  const choice = reactive<{ memberId: string | null; creating: boolean; newName: string }>({
    memberId: null,
    creating: false,
    newName: '',
  })
  const nameErrorKey = ref<string | null>(null)
  const submitError = ref<unknown>(null)
  const submitting = ref(false)
  let token = ''
  let loadId = 0
  let previewController: AbortController | null = null

  async function load(): Promise<void> {
    previewController?.abort()
    const controller = new AbortController()
    previewController = controller
    const currentId = ++loadId
    phase.value = 'loading'
    try {
      const next = await api.post<JoinPreview>('/join/preview', { token }, { signal: controller.signal })
      if (currentId !== loadId || controller.signal.aborted) return
      preview.value = next
      phase.value = 'ready'
    } catch (caught) {
      if (currentId !== loadId || controller.signal.aborted) return
      if (caught instanceof ApiError && caught.status === 404) {
        phase.value = 'gone'
      } else {
        failure.value = caught
        phase.value = 'failed'
      }
    } finally {
      if (previewController === controller) previewController = null
    }
  }

  /** Validates and loads an invite link, fragment, or raw token string. */
  function start(raw: string): boolean {
    const found = extractToken(raw)
    if (found === null) return false
    token = found
    void load()
    return true
  }

  function body(): JoinRequest | null {
    if (!choice.creating) return choice.memberId === null ? null : { token, member_id: choice.memberId }
    const others = (preview.value?.members ?? []).map((member) => member.display_name)
    const checked = checkMemberName(choice.newName, others)
    if ('error' in checked) {
      nameErrorKey.value = `members.errors.${checked.error}`
      return null
    }
    return { token, new_name: checked.name }
  }

  async function submit(): Promise<void> {
    if (submitting.value) return
    nameErrorKey.value = null
    submitError.value = null
    const request = body()
    if (request === null) return
    submitting.value = true
    try {
      const joined = await api.post<TripDetail>('/join', request)
      await router.replace(`/trips/${encodeURIComponent(joined.id)}`)
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 404) phase.value = 'gone'
      else submitError.value = caught
    } finally {
      submitting.value = false
    }
  }

  async function openTrip(): Promise<void> {
    if (preview.value) await router.replace(`/trips/${encodeURIComponent(preview.value.trip.id)}`)
  }

  function consumeFragment(): void {
    const fragment = location.hash
    if (fragment === '') return
    // Preserve Vue Router's history state while stripping the secret token from the address bar.
    history.replaceState(history.state, '', location.pathname + location.search)
    preview.value = undefined
    if (!start(fragment)) phase.value = 'gone'
  }

  if (getCurrentScope()) {
    onScopeDispose(() => {
      loadId += 1
      previewController?.abort()
      previewController = null
    })
  }

  consumeFragment()
  watch(() => route.hash, consumeFragment)

  return { phase, preview, failure, choice, nameErrorKey, submitError, submitting, start, load, submit, openTrip }
}
