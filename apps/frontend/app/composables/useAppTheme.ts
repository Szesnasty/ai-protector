import { computed, onMounted } from 'vue'
import { useTheme } from 'vuetify'

export const useAppTheme = () => {
  const theme = useTheme()
  const isDark = computed(() => theme.global.current.value.dark)

  const toggle = () => {
    theme.global.name.value = isDark.value ? 'light' : 'dark'
    localStorage.setItem('ai-protector-theme', theme.global.name.value)
  }

  onMounted(() => {
    const saved = localStorage.getItem('ai-protector-theme')
    if (saved && ['dark', 'light'].includes(saved)) {
      theme.global.name.value = saved
    }
  })

  return { isDark, toggle }
}
