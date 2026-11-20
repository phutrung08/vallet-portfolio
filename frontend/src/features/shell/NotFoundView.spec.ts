import { describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { RouterView, createMemoryHistory, createRouter } from 'vue-router'
import NotFoundView from '@/features/shell/NotFoundView.vue'
import { createAppI18n } from '@/lib/i18n'
import enRaw from '@/locales/en.json?raw'
import viRaw from '@/locales/vi.json?raw'

// Parse JSON source text directly since the i18n Vite plugin pre-compiles locale imports.
const en = JSON.parse(enRaw) as { notFound: { title: string; home: string } }
const vi = JSON.parse(viRaw) as { notFound: { title: string; home: string } }

describe('NotFoundView', () => {
  it.each([
    ['en', en.notFound],
    ['vi', vi.notFound],
  ] as const)('renders %s title and home link for an unknown route', async (locale, texts) => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/:pathMatch(.*)*', component: NotFoundView },
      ],
    })
    await router.push('/no/such/page')
    await router.isReady()
    const wrapper = mount(RouterView, { global: { plugins: [router, createAppI18n(locale)] } })
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe(texts.title)
    const link = wrapper.get('a')
    expect(link.attributes('href')).toBe('/')
    expect(link.text()).toBe(texts.home)
  })
})
