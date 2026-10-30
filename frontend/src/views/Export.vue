<template>
  <div class="card">
    <div style="display:flex; align-items:center; justify-content:space-between;">
      <div style="font-weight:700;">数据导出</div>
    </div>

    <div style="height: 12px"></div>

    <el-row :gutter="12">
      <el-col :span="8">
        <el-input v-model="filters.keyword" placeholder="关键词（标题/作者/原文/标签/来源）" clearable />
      </el-col>
      <el-col :span="4">
        <el-select v-model="filters.status" placeholder="状态" clearable style="width:100%;">
          <el-option label="待校对" value="待校对" />
          <el-option label="待提取" value="待提取" />
          <el-option label="已入库" value="已入库" />
          <el-option label="需复核" value="需复核" />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-input v-model="filters.dynasty" placeholder="朝代" clearable />
      </el-col>
      <el-col :span="8" style="display:flex; gap:10px;">
        <el-button type="primary" :loading="loading" @click="downloadRecords('json')">导出记录JSON</el-button>
        <el-button :loading="loading" @click="downloadRecords('csv')">导出记录CSV</el-button>
      </el-col>
    </el-row>

    <div style="height: 12px"></div>

    <el-row :gutter="12">
      <el-col :span="8">
        <el-input v-model="tripleSubject" placeholder="三元组主体过滤（如：鲁迅）" clearable />
      </el-col>
      <el-col :span="16" style="display:flex; gap:10px;">
        <el-button type="primary" :loading="loading" @click="downloadTriples('json')">导出三元组JSON</el-button>
        <el-button :loading="loading" @click="downloadTriples('csv')">导出三元组CSV</el-button>
      </el-col>
    </el-row>

    <div style="height: 12px"></div>

    <el-alert
      type="info"
      :closable="false"
      title="说明"
      description="导出接口会在后端生成文件并直接下载。若数据量很大，建议按状态/朝代/关键词先筛选。"
      show-icon
    />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { http } from "../api/client";

const emit = defineEmits(["set-title"]);

const filters = reactive({ keyword: "", status: "", dynasty: "" });
const tripleSubject = ref("");
const loading = ref(false);

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

async function downloadRecords(format) {
  loading.value = true;
  try {
    const res = await http.get("/api/export/records", {
      params: { format, ...filters },
      responseType: "blob"
    });
    const filename = format === "csv" ? "records.csv" : "records.json";
    downloadBlob(res.data, filename);
    ElMessage.success("已开始下载");
  } catch (e) {
    ElMessage.error("导出失败");
  } finally {
    loading.value = false;
  }
}

async function downloadTriples(format) {
  loading.value = true;
  try {
    const res = await http.get("/api/export/triples", {
      params: { format, subject: tripleSubject.value || undefined },
      responseType: "blob"
    });
    const filename = format === "csv" ? "triples.csv" : "triples.json";
    downloadBlob(res.data, filename);
    ElMessage.success("已开始下载");
  } catch (e) {
    ElMessage.error("导出失败");
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  emit("set-title", { title: "数据导出", sub: "导出 JSON / CSV" });
});
</script>

