<script setup>
defineProps(['layout', 'items', 'selected', 'activeTab', 'tableStrategy', 'showLines', 'showBoxes', 'showTables', 'extraLayers', 'search', 'camelotCount', 'camelotBusy', 'camelotError', 'doclayoutCount', 'doclayoutBusy', 'doclayoutError', 'doclayoutThreshold', 'inspectSettings', 'inspectResult', 'inspectBusy', 'inspectError', 'cropBox', 'inspectScope', 'searchTerm', 'soloType'])
const emit = defineEmits(['update:activeTab', 'update:tableStrategy', 'update:showLines', 'update:showBoxes', 'update:showTables', 'update:extraLayers', 'update:search', 'update:doclayoutThreshold', 'update:inspectSettings', 'update:inspectScope', 'resetInspect', 'searchInspect', 'soloLayer', 'select'])
const parameters = { snap_tolerance: '吸附 Snap', join_tolerance: '连接 Join', intersection_tolerance: '交点 Intersection', edge_min_length: '最短边 Edge' }
const groups = [
  { title: '文字与布局', layers: { words: 'Words · 单词', chars: 'Chars · 字符', bold: 'Bold · 粗体', matches: '搜索命中' } },
  { title: '绘图与图像', layers: { strokes: 'Lines · 直线', rects: 'Rects · 矩形', curves: 'Curves · 曲线', edges: 'Edges · 边缘', images: 'Images · 图像' } },
  { title: '表格调试', layers: { tableEdges: '候选 Edges', intersections: 'Intersections · 交点', cells: 'Cells · 单元格' } },
  { title: '文档结构', layers: { hyperlinks: 'Hyperlinks · 链接', annotations: 'Annotations · 注释' } },
]
function count(layout, type, strategy) {
  if (!layout) return 0
  if (type === 'bold') return (layout.chars || []).filter(item => /bold|black|heavy|semibold|demibold/i.test(item.properties?.fontname || '')).length
  if (['words', 'chars', 'images', 'matches', 'hyperlinks', 'annotations'].includes(type)) return layout[type]?.length ?? 0
  if (['tableEdges', 'intersections', 'cells'].includes(type)) return layout.table_debug?.[strategy]?.[type === 'tableEdges' ? 'edges' : type]?.length ?? 0
  return layout.strokes?.[type === 'strokes' ? 'lines' : type]?.length ?? 0
}
function toggleLayer(layers, type, checked) {
  emit('update:extraLayers', { ...layers, [type]: checked })
}
</script>

<template>
  <aside class="inspector element-panel">
    <div class="inspector-head">
      <div class="engine-tabs"><button :class="{active: activeTab === 'pdfplumber'}" @click="emit('update:activeTab', 'pdfplumber')">pdfplumber</button><button :class="{active: activeTab === 'camelot'}" @click="emit('update:activeTab', 'camelot')">Camelot</button><button :class="{active: activeTab === 'doclayout'}" @click="emit('update:activeTab', 'doclayout')">PP-DocLayout-M</button></div>
      <div v-if="activeTab === 'camelot'" class="strategy-picker"><label for="camelot-strategy">Table detection</label><select id="camelot-strategy" :value="tableStrategy" @change="emit('update:tableStrategy', $event.target.value)"><option value="stream">Stream</option><option value="network">Network</option><option value="lattice">Lattice</option><option value="hybrid">Hybrid</option></select></div>
      <div v-else-if="activeTab === 'doclayout'" class="strategy-picker"><label for="doclayout-threshold">表格置信度 ≥ {{ Number(doclayoutThreshold).toFixed(2) }}</label><input id="doclayout-threshold" aria-label="表格置信度阈值" type="range" min="0.1" max="0.95" step="0.05" :value="doclayoutThreshold" @change="emit('update:doclayoutThreshold', Number($event.target.value))"></div>
      <div v-else class="strategy-picker"><label for="table-strategy">Table detection</label><select id="table-strategy" :value="tableStrategy" @change="emit('update:tableStrategy', $event.target.value)"><option value="lines">lines · 有线表格</option><option value="text">text · 无线表格</option></select></div>
      <div class="inspector-title-row"><h2>布局元素</h2><span class="count-badge">{{ items.length }}</span></div>
      <p class="panel-subtitle">{{ doclayoutBusy && activeTab === 'doclayout' ? '正在运行 PP-DocLayout-M ONNX（CPU）…' : camelotBusy && activeTab === "camelot" ? "正在运行 Camelot " + tableStrategy + "…" : "查找并定位当前页文本结构" }}</p><p v-if="activeTab === 'camelot' && camelotError" class="engine-note" role="alert">{{ camelotError }}</p><p v-if="activeTab === 'doclayout' && doclayoutError" class="engine-note" role="alert">{{ doclayoutError }}</p>
      <div class="search-wrap">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"></circle><path d="m16 16 5 5"></path></svg>
        <input :value="search" @input="emit('update:search', $event.target.value)" aria-label="搜索文字内容" placeholder="搜索文字内容…" :disabled="!layout">
        <button v-if="search" class="clear-search" aria-label="清除搜索" @click="emit('update:search', '')">×</button>
      </div>
      <div class="filter-counts">
        <label v-if="activeTab === 'pdfplumber'"><input type="checkbox" :checked="showLines" @change="emit('update:showLines', $event.target.checked)"> <span class="legend-dot red"></span> Lines {{ layout?.lines.length ?? 0 }}</label>
        <label v-if="activeTab === 'pdfplumber'"><input type="checkbox" :checked="showBoxes" @change="emit('update:showBoxes', $event.target.checked)"> <span class="legend-dot blue"></span> Boxes {{ layout?.textboxes.length ?? 0 }}</label>
        <label><input type="checkbox" :checked="showTables" @change="emit('update:showTables', $event.target.checked)"> <span class="legend-dot green"></span> Tables {{ activeTab === 'doclayout' ? doclayoutCount : activeTab === 'camelot' ? camelotCount : (layout?.tables?.[tableStrategy]?.length ?? 0) }}</label>
      </div>
      <div v-if="activeTab === 'pdfplumber'" class="layer-groups">
        <section v-for="group in groups" :key="group.title" class="layer-group">
          <div class="layer-heading">{{ group.title }}</div>
          <div class="layer-options">
            <label v-for="(name, type) in group.layers" :key="type">
              <input type="checkbox" :checked="extraLayers[type]" @change="toggleLayer(extraLayers, type, $event.target.checked)">
              <span>{{ name }}</span><small>{{ count(layout, type, tableStrategy) }}</small><button class="solo-layer" :title="'只显示 ' + name" @click.stop.prevent="emit('soloLayer', type)">{{ soloType === type ? '恢复' : '独看' }}</button>
            </label>
          </div>
        </section>
      </div>
      <section v-if="activeTab === 'pdfplumber'" class="inspect-controls">
        <div class="layer-heading">解析范围</div>
        <div class="scope-picker">
          <button :class="{ active: inspectScope === 'page' }" @click="emit('update:inspectScope', 'page')">整页</button>
          <button :disabled="!cropBox" :class="{ active: inspectScope === 'crop' }" @click="emit('update:inspectScope', 'crop')">局部</button>
        </div>
        <p class="inspect-status">{{ inspectError ? '解析失败：' + inspectError : inspectBusy ? '解析中…' : inspectResult ? (inspectScope === 'crop' ? '局部解析完成' : '整页解析完成') : '尚未取得结果' }}</p>
        <div class="layer-heading">原文搜索（回车定位）</div>
        <form class="search-wrap" @submit.prevent="emit('searchInspect', $event.target.elements.query.value.trim())">
          <input name="query" type="text" :value="searchTerm" placeholder="查找 PDF 文字" maxlength="100">
          <button type="submit" class="solo-layer">查找</button>
        </form>
        <div class="layer-heading">表格检测参数 <button @click="emit('resetInspect')">恢复默认</button></div>
        <label v-for="(name, key) in parameters" :key="key" class="inspect-setting">
          <span>{{ name }}</span>
          <input type="number" min="0" max="30" step="0.5" :value="inspectSettings[key]" @change="emit('update:inspectSettings', { ...inspectSettings, [key]: Math.max(0, Math.min(30, Number($event.target.value) || 0)) })">
        </label>
        <p class="inspect-status">{{ inspectBusy ? '正在重新计算…' : inspectError || (inspectResult ? '解析耗时 ' + inspectResult.elapsed_ms + ' ms' : '使用默认检测结果') }}</p>
        <p v-if="cropBox" class="inspect-status">局部区域：{{ cropBox.map(v => v.toFixed(1)).join(', ') }}</p>
        <div v-if="inspectResult" class="inspect-text">
          <div class="layer-heading">文字提取对比</div>
          <details><summary>普通 extract_text()</summary><pre>{{ inspectResult.text.normal }}</pre></details>
          <details><summary>布局 extract_text(layout=True)</summary><pre>{{ inspectResult.text.layout }}</pre></details>
          <details><summary>去重 dedupe_chars()</summary><pre>{{ inspectResult.text.deduped }}</pre></details>
        </div>
      </section>
    </div>
    <div class="element-list">
      <template v-if="items.length">
        <button v-for="(item, index) in items" :key="item.id" class="element-item" :class="{ active: selected === item.id }" @click="emit('select', item)">
          <span class="element-index">{{ String(index + 1).padStart(2, '0') }}</span>
          <span class="element-text"><span class="element-preview">{{ item.text }}</span><span class="element-type">{{ item.type === 'lines' ? 'TEXT LINE' : item.type === 'tables' ? 'TABLE · ' + (activeTab === 'doclayout' ? 'ONNX' : tableStrategy.toUpperCase()) : item.type === 'textboxes' ? 'LT TEXT BOX' : item.type.toUpperCase() }}</span></span>
        </button>
      </template>
      <div v-else class="list-empty">{{ activeTab === 'doclayout' ? (doclayoutBusy ? '正在运行 CPU 模型…' : doclayoutError ? '模型运行失败，请查看错误' : '当前页未定位到置信度达标的表格') : activeTab === 'camelot' ? (camelotBusy ? '正在识别当前页表格…' : camelotError ? '解析失败，请查看上方错误' : !showTables ? '请勾选 Tables 以显示检测结果' : '当前页使用 ' + tableStrategy.toUpperCase() + ' 未检测到表格，可尝试其他策略') : layout ? '没有匹配的文字元素' : '打开 PDF 后显示布局候选' }}</div>
    </div>
  </aside>
</template>
