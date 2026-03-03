import { computed } from 'vue'
import { useField } from 'vee-validate'

/**
 * Wraps useField() and returns props compatible with Vuetify inputs.
 * Usage: <v-text-field v-bind="field" />
 */
export function useVuetifyField(name: string) {
  const { value, errorMessage, handleBlur } = useField<string>(name)

  const field = computed(() => ({
    modelValue: value.value,
    'onUpdate:modelValue': (v: string) => { value.value = v },
    errorMessages: errorMessage.value ? [errorMessage.value] : [],
    onBlur: handleBlur,
  }))

  return { field, value, errorMessage }
}
