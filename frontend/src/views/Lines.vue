<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const draft = ref<Record<number, string>>({})
const saving = ref<number | null>(null)
async function load() { rows.value = await api('/lines') }
onMounted(load)
async function save(line: any, names: string[]) {
  saving.value = line.id
  try {
    await api(`/lines/${line.id}/shared_stops`, { method: 'PUT', body: JSON.stringify({ stop_names: names }) })
    await load()
  } finally { saving.value = null }
}
function addStop(line: any) {
  const name = (draft.value[line.id] || '').trim()
  if (!name) return
  const names: string[] = [...(line.shared_stops || [])]
  if (!names.includes(name)) names.push(name)
  draft.value[line.id] = ''
  save(line, names)
}
function removeStop(line: any, name: string) {
  save(line, (line.shared_stops || []).filter((n: string) => n !== name))
}
</script>
<template>
  <h1>线路</h1>
  <p class="sub">运营线路与串车 / 大间隔判定阈值 · 登记共用站后该站并入各线到站做跨线判定</p>
  <div class="card">
    <table>
      <thead><tr><th>编码</th><th>名称</th><th>计划间隔(分)</th><th>串车阈值</th><th>大间隔阈值</th><th>共用站（跨线判定）</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.code }}</td><td>{{ r.name }}</td><td>{{ r.planned_headway_min }}</td><td>{{ r.bunch_threshold }}</td><td>{{ r.large_threshold }}</td>
          <td>
            <span v-for="s in r.shared_stops" :key="s" class="chip">
              {{ s }}<button class="chip-x" :disabled="saving === r.id" title="移除" @click="removeStop(r, s)">×</button>
            </span>
            <span v-if="!r.shared_stops?.length" class="muted">无</span>
            <input v-model="draft[r.id]" class="chip-input" placeholder="站名" @keyup.enter="addStop(r)" />
            <button class="btn btn-mini" :disabled="saving === r.id" @click="addStop(r)">添加</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <p class="muted">多条线路登记同一站名后，该站检测时会把各共用线的到站并入同一时间序；未登记的站只检本线。</p>
</template>
