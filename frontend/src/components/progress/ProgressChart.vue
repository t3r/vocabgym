<template>
  <div class="relative" style="height: 250px;">
    <Bar v-if="type === 'bar'" :data="data" :options="chartOptions" />
    <Line v-else :data="data" :options="chartOptions" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import { Bar, Line } from 'vue-chartjs'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const props = defineProps({
  data: { type: Object, required: true },
  type: { type: String, default: 'bar', validator: (v) => ['bar', 'line'].includes(v) }
})

const hasMultipleDatasets = computed(() => (props.data?.datasets?.length || 0) > 1)
const hasDualAxis = computed(() => props.data?.datasets?.some(d => d.yAxisID === 'y1'))

const chartOptions = computed(() => {
  const opts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: hasMultipleDatasets.value,
        labels: {
          usePointStyle: true,
          pointStyle: 'line',
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: { precision: 0 },
      },
    },
  }

  if (hasDualAxis.value) {
    opts.scales.y1 = {
      beginAtZero: true,
      position: 'right',
      max: 100,
      ticks: {
        callback: (v) => v + '%',
      },
      grid: { drawOnChartArea: false },
    }
  }

  return opts
})
</script>
