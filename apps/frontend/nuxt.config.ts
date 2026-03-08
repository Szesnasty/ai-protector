// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  modules: [
    'vuetify-nuxt-module',
    '@pinia/nuxt',
    '@nuxt/eslint',
    // vuetify-nuxt-module pushes `vuetify/styles` and `@mdi/font/css/…` to
    // nuxt.options.css.  In SSR dev mode those raw module-name entries become
    // bare /_nuxt/… <link> tags that 404 (the same styles also load correctly
    // via @fs links resolved by Vite).  Strip them and load via JS import in
    // app/plugins/vuetify-styles.client.ts so Vite resolves them properly.
    function (_opts: unknown, nuxt: { options: { css: (string | object)[] } }) {
      nuxt.options.css = nuxt.options.css.filter(
        c => typeof c !== 'string'
          || (c !== 'vuetify/styles'
              && c !== 'vuetify/lib/styles/main.css'
              && c !== '@mdi/font/css/materialdesignicons.css'),
      )
    },
  ],

  css: [],

  vuetify: {
    moduleOptions: {
      styles: 'sass',
    },
    vuetifyOptions: {
      theme: {
        defaultTheme: 'dark',
        themes: {
          dark: {
            colors: {
              primary: '#5C6BC0',
              secondary: '#26A69A',
              error: '#EF5350',
              warning: '#FFA726',
              success: '#66BB6A',
              background: '#121212',
              surface: '#1E1E1E',
            },
          },
          light: {
            colors: {
              primary: '#3F51B5',
              secondary: '#009688',
              error: '#F44336',
              warning: '#FF9800',
              success: '#4CAF50',
            },
          },
        },
      },
      icons: {
        defaultSet: 'mdi',
      },
    },
  },

  runtimeConfig: {
    public: {
      apiBase: 'http://localhost:8000',
      agentApiBase: 'http://localhost:8002',
      openaiApiBase: 'https://api.openai.com',
      mistralApiBase: 'https://api.mistral.ai',
    },
  },

  typescript: {
    strict: true,
  },
})
