// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

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
              primary: '#7986CB',
              secondary: '#4DB6AC',
              error: '#EF5350',
              warning: '#FFB74D',
              success: '#81C784',
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
              primary: '#3F51B5',
              secondary: '#009688',
              error: '#F44336',
              warning: '#FF9800',
              success: '#4CAF50',
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
      openaiApiBase: 'https://api.openai.com',
      mistralApiBase: 'https://api.mistral.ai',
    },
  },

  typescript: {
    strict: true,
  },
})
