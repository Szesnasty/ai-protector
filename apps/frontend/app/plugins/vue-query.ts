import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import type { VueQueryPluginOptions } from '@tanstack/vue-query'

export default defineNuxtPlugin((nuxtApp) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: 1,
        refetchOnWindowFocus: true,
      },
    },
  })

  const options: VueQueryPluginOptions = { queryClient }

  nuxtApp.vueApp.use(VueQueryPlugin, options)
})
