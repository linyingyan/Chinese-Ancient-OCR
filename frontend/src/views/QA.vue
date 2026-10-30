<template>
  <div class="card">
    <div style="font-weight:700;">历史问题咨询</div>
    <div style="height: 12px"></div>

    <el-row :gutter="12">
      <el-col :span="10">
        <el-select v-model="recordId" filterable style="width:100%;" placeholder="选择背景文献">
          <el-option
            v-for="r in records"
            :key="r.id"
            :label="`${r.title || r.source_name || '未命名'} (ID:${r.id})`"
            :value="r.id"
          />
        </el-select>
      </el-col>
      <el-col :span="14" style="display:flex; gap:10px;">
        <el-input v-model="question" placeholder="例如：鲁迅在广州发生了什么？" />
        <el-button type="primary" :loading="loading" @click="ask" :disabled="!recordId || !question.trim()">
          提问
        </el-button>
      </el-col>
    </el-row>

    <div style="height: 14px"></div>

    <el-row :gutter="12">
      <el-col :span="10">
        <div style="font-weight:600; margin-bottom:8px;">文本分段</div>
        <el-scrollbar height="520px" style="border:1px solid rgba(0,0,0,0.08); border-radius:12px;">
          <div style="padding:10px;">
            <el-collapse v-model="activeNames">
              <el-collapse-item
                v-for="c in chunks"
                :key="c.id"
                :name="String(c.id)"
                :title="`段落 ${c.chunk_index + 1}`"
              >
                <div style="white-space: pre-wrap;">{{ c.content }}</div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-scrollbar>
      </el-col>
      <el-col :span="14">
        <div style="font-weight:600; margin-bottom:8px;">专家回答</div>
        <el-input
          v-model="answer"
          type="textarea"
          :autosize="{ minRows: 18, maxRows: 26 }"
          placeholder="回答会显示在这里（需在系统设置配置可用大模型接口）"
        />
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { http } from "../api/client";

const emit = defineEmits(["set-title"]);

const records = ref([]);
const recordId = ref(null);
const question = ref("");
const answer = ref("");
const loading = ref(false);
const chunks = ref([]);
const activeNames = ref([]);

async function loadRecords() {
  const res = await http.get("/api/records", { params: { skip: 0, limit: 200 } });
  records.value = res.data.items || [];
  if (!recordId.value && records.value.length) recordId.value = records.value[0].id;
}

async function loadChunks() {
  if (!recordId.value) return;
  const res = await http.get(`/api/records/${recordId.value}/chunks`);
  chunks.value = res.data || [];
  activeNames.value = [];
}

async function ask() {
  loading.value = true;
  try {
    const res = await http.post("/api/qa", { record_id: recordId.value, question: question.value });
    answer.value = res.data.answer || "";
    ElMessage.success("已回答");
  } catch (e) {
    ElMessage.error("问答失败（请检查大模型配置或接口可用性）");
  } finally {
    loading.value = false;
  }
}

watch(recordId, () => {
  loadChunks();
});

onMounted(() => {
  emit("set-title", { title: "历史问答", sub: "基于文献的事件检索" });
  loadRecords().then(loadChunks);
});
</script>

