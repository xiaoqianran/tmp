<script setup>
defineProps(['layout', 'items', 'selected', 'activeTab', 'tableStrategy', 'showLines', 'showBoxes', 'showTables', 'search', 'camelotCount', 'camelotBusy', 'camelotError'])
const emit = defineEmits(['update:activeTab', 'update:tableStrategy', 'update:showLines', 'update:showBoxes', 'update:showTables', 'update:search', 'select'])
</script>

<template>
  <aside class="inspector element-panel">
    <div class="inspector-head">
      <div class="engine-tabs"><button :class="{active: activeTab === 'pdfplumber'}" @click="emit('update:activeTab', 'pdfplumber')">pdfplumber</button><button :class="{active: activeTab === 'camelot'}" @click="emit('update:activeTab', 'camelot')">Camelot</button></div>
      <div v-if="activeTab === 'camelot'" class="strategy-picker"><label for="camelot-strategy">Table detection</label><select id="camelot-strategy" :value="tableStrategy" @change="emit('update:tableStrategy', $event.target.value)"><option value="stream">Stream</option><option value="network">Network</option><option value="lattice">Lattice</option><option value="hybrid">Hybrid</option></select></div>
      <div v-else class="strategy-picker"><label for="table-strategy">Table detection</label><select id="table-strategy" :value="tableStrategy" @change="emit('update:tableStrategy', $event.target.value)"><option value="lines">lines · 有线表格</option><option value="text">text · 无线表格</option></select></div>
      <div class="inspector-title-row"><h2>布局元素</h2><span class="count-badge">{{ items.length }}</span></div>
      <p class="panel-subtitle">{{ camelotBusy && activeTab === "camelot" ? "正在运行 Camelot " + tableStrategy + "…" : "查找并定位当前页文本结构" }}</p><p v-if="activeTab === 'camelot' && camelotError" class="engine-note" role="alert">{{ camelotError }}</p>
      <div class="search-wrap">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"></circle><path d="m16 16 5 5"></path></svg>
        <input :value="search" @input="emit('update:search', $event.target.value)" aria-label="搜索文字内容" placeholder="搜索文字内容…" :disabled="!layout">
        <button v-if="search" class="clear-search" aria-label="清除搜索" @click="emit('update:search', '')">×</button>
      </div>
      <div class="filter-counts">
        <label><input type="checkbox" :checked="showLines" @change="emit('update:showLines', $event.target.checked)"> <span class="legend-dot red"></span> Lines {{ layout?.lines.length ?? 0 }}</label>
        <label><input type="checkbox" :checked="showBoxes" @change="emit('update:showBoxes', $event.target.checked)"> <span class="legend-dot blue"></span> Boxes {{ layout?.textboxes.length ?? 0 }}</label>
        <label><input type="checkbox" :checked="showTables" @change="emit('update:showTables', $event.target.checked)"> <span class="legend-dot green"></span> Tables {{ activeTab === 'camelot' ? camelotCount : (layout?.tables?.[tableStrategy]?.length ?? 0) }}</label>
      </div>
    </div>
    <div class="element-list">
      <template v-if="items.length">
        <button v-for="(item, index) in items" :key="item.id" class="element-item" :class="{ active: selected === item.id }" @click="emit('select', item)">
          <span class="element-index">{{ String(index + 1).padStart(2, '0') }}</span>
          <span class="element-text"><span class="element-preview">{{ item.text }}</span><span class="element-type">{{ item.type === 'lines' ? 'TEXT LINE' : item.type === 'tables' ? 'TABLE · ' + tableStrategy.toUpperCase() : 'LT TEXT BOX' }}</span></span>
        </button>
      </template>
      <div v-else class="list-empty">{{ layout ? '没有匹配的文字元素' : '打开 PDF 后显示布局候选' }}</div>
    </div>
  </aside>
</template>
