/**
 * Import Vuetify base styles and MDI icon font via JavaScript so that
 * Vite resolves them to proper @fs paths in dev mode.
 *
 * We intentionally keep these out of the Nuxt `css` config array because
 * entries there also generate bare SSR <link> tags (e.g.
 * /_nuxt/vuetify/styles) that 404 in the Vite dev server — even though
 * the same styles load correctly via @fs-resolved duplicates.
 */
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'

export default defineNuxtPlugin(() => {})
