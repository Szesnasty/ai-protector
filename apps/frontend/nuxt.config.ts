// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  modules: [
    'vuetify-nuxt-module',
    '@pinia/nuxt',
    '@nuxt/eslint',
  ],

  vuetify: {
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
    },
  },

  typescript: {
    strict: true,
  },
})
