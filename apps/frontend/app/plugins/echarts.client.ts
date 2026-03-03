/**
 * Echarts plugin — register renderer and chart types for vue-echarts.
 *
 * vue-echarts 8 / echarts 6 require explicit registration of the canvas
 * renderer and every chart type / component that the app uses.
 */
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components'

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
])

export default defineNuxtPlugin(() => {
  // registration is side-effect only — nothing to provide
})
