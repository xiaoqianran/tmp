<script setup>
defineProps(['layout', 'item', 'tableStrategy'])
const emit = defineEmits(['export', 'copy'])
</script>

<template>
  <aside class="inspector detail-sidebar">
    <div class="detail-title">
      <div><h2>元素详情</h2><p class="panel-subtitle">选中标注后显示完整内容和坐标</p></div>
      <button class="export-link" :disabled="!layout" @click="emit('export')">导出 JSON ↗</button>
    </div>
    <div v-if="item" class="detail-body">
      <div class="detail-chip" :class="item.type">{{ item.type === 'lines' ? 'Text Line' : item.type === 'tables' ? 'Table · ' + tableStrategy : 'LTTextBox' }}</div>
      <div class="section-label">完整文字</div>
      <div class="detail-content">{{ item.text }}</div>
      <template v-if="item.type === 'tables'"><div class="section-label">提取的表格结构</div><pre class="detail-content table-data">{{ JSON.stringify(item.data, null, 2) }}</pre></template>
      <div class="section-label">边界坐标 · BBox</div>
      <div class="bbox-grid">
        <div v-for="(axis, index) in ['x0','top','x1','bottom']" :key="axis"><span>{{ axis }}</span><strong>{{ item.bbox[index].toFixed(2) }}</strong></div>
      </div>
      <button class="button subtle copy-detail" @click="emit('copy')">复制文字</button>
    </div>
    <div v-else class="detail-placeholder">点击中间 PDF 标注框，或在左侧元素列表中选取条目。</div>
  </aside>
</template>
