// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  // SPA mode — this is a dashboard app with no SEO needs.
  // Avoids hydration mismatches from browser-only APIs
  // (DOMPurify, localStorage, sessionStorage) used throughout.
  ssr: false,

  modules: [
    'vuetify-nuxt-module',
    '@pinia/nuxt',
    '@nuxt/eslint',
  ],

  css: ['~/assets/global.scss'],

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
              primary: '#7C8FD4',
              secondary: '#4DB6AC',
              info: '#38BDF8',
              error: '#EF4444',
              warning: '#F59E0B',
              success: '#22C55E',
              background: '#1A1A2E',
              surface: '#252540',
              'surface-bright': '#333352',
              'surface-light': '#2A2A48',
              'surface-variant': '#B0B0C0',
              'on-surface-variant': '#252540',
            },
          },
          light: {
            colors: {
              primary: '#4F5FB5',
              secondary: '#009688',
              info: '#0EA5E9',
              error: '#DC2626',
              warning: '#D97706',
              success: '#16A34A',
              background: '#F5F5F5',
              surface: '#FFFFFF',
              'surface-bright': '#FFFFFF',
              'surface-light': '#EEEEEE',
              'surface-variant': '#424242',
              'on-surface-variant': '#EEEEEE',
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
      testAgentPythonUrl: 'http://localhost:8003',
      testAgentGraphUrl: 'http://localhost:8004',
      openaiApiBase: 'https://api.openai.com',
      mistralApiBase: 'https://api.mistral.ai',
    },
  },

  typescript: {
    strict: true,
  },
})
