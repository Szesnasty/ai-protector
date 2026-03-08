/**
 * Strip duplicate CSS <link> tags that produce 404s in Vite dev mode.
 *
 * vuetify-nuxt-module adds `vuetify/styles` and `@mdi/font/css/…` to the
 * Nuxt `css[]` array.  During SSR, Nuxt renders **two** `<link>` tags for
 * each entry:
 *
 *   1. A bare path  `/_nuxt/vuetify/styles`                      → 404
 *   2. A Vite @fs   `/_nuxt/@fs/…/vuetify/lib/styles/main.css`   → 200
 *
 * #2 already delivers all the styles the browser needs.
 * This plugin removes the bare #1 links so the console stays clean
 * and SSR still ships CSS (no FOUC).
 */
export default defineNitroPlugin((nitro) => {
  // Only matters in dev — production builds bundle CSS into hashed chunks.
  if (!import.meta.dev) return

  nitro.hooks.hook('render:html', (html) => {
    const bare404 = [
      '/_nuxt/vuetify/styles',
      '/_nuxt/@mdi/font/css/materialdesignicons.css',
      '/_nuxt/vuetify/lib/styles/main.css',
    ]

    html.head = html.head.map((chunk) => {
      for (const href of bare404) {
        // Match <link … href="/_nuxt/vuetify/styles" …>
        chunk = chunk.replace(
          new RegExp(`<link[^>]*href="${href.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"[^>]*>`, 'g'),
          '',
        )
      }
      return chunk
    })
  })
})
