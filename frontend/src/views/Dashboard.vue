<template>
  <div class="card">
    <el-row :gutter="12">
      <el-col :span="6">
        <el-statistic title="总记录数" :value="metrics.total" />
      </el-col>
      <el-col :span="6">
        <el-statistic title="待校对" :value="metrics.pending" />
      </el-col>
      <el-col :span="6">
        <el-statistic title="已入库" :value="metrics.done" />
      </el-col>
      <el-col :span="6">
        <el-statistic title="知识三元组" :value="metrics.triples" />
      </el-col>
    </el-row>
  </div>

  <div style="height: 12px"></div>

  <div class="card">
    <div style="display:flex; align-items:center; justify-content:space-between;">
      <div style="font-weight:700;">最近记录</div>
      <el-button type="primary" @click="$router.push('/ocr')">去OCR校对</el-button>
    </div>
    <div style="height: 10px"></div>
    <el-table :data="records" border style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column prop="author" label="作者" width="120" />
      <el-table-column prop="dynasty" label="朝代" width="120" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="source_name" label="来源" min-width="160" />
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { http } from "../api/client";

const emit = defineEmits(["set-title"]);

const metrics = ref({ total: 0, pending: 0, done: 0, triples: 0 });
const records = ref([]);

async function load() {
  const list = await http.get("/api/records", { params: { skip: 0, limit: 10 } });
  records.value = list.data.items || [];
  metrics.value.total = list.data.total || 0;
  metrics.value.pending = records.value.filter((r) => r.status === "待校对").length;
  metrics.value.done = records.value.filter((r) => r.status === "已入库").length;
  const triples = await http.get("/api/triples", { params: { skip: 0, limit: 1 } });
  metrics.value.triples = triples.data.total || 0;
}

onMounted(() => {
  emit("set-title", { title: "首页", sub: "系统概览" });
  load();
});
</script>

