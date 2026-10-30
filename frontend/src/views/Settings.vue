<template>
  <div class="card">
    <div style="display:flex; align-items:center; justify-content:space-between;">
      <div style="font-weight:700;">系统设置</div>
      <el-button type="primary" @click="save">保存</el-button>
    </div>

    <div style="height: 12px"></div>

    <el-form label-width="120px">
      <el-form-item label="提供方">
        <el-select v-model="provider" style="width: 100%">
          <el-option label="通义千问（Qwen / DashScope 兼容）" value="qwen" />
          <el-option label="OpenAI 官方" value="openai" />
          <el-option label="Groq（OpenAI 兼容）" value="groq" />
          <el-option label="本地 LM Studio（OpenAI 兼容）" value="lmstudio" />
          <el-option label="本地 vLLM（OpenAI 兼容）" value="vllm" />
          <el-option label="自定义" value="custom" />
        </el-select>
      </el-form-item>
      <el-form-item label="API Key">
        <el-input v-model="apiKey" type="password" show-password />
      </el-form-item>
      <el-form-item label="Base URL">
        <el-input v-model="baseUrl" placeholder="https://api.openai.com/v1 或 http://localhost:1234/v1" />
      </el-form-item>
      <el-form-item label="模型名">
        <el-input v-model="model" placeholder="gpt-4o-mini 或本地模型名" />
      </el-form-item>
    </el-form>

    <div style="display:flex; gap:10px;">
      <el-button :loading="testing" @click="test">连通性测试</el-button>
      <el-button @click="reset">重置</el-button>
    </div>

    <div style="height: 12px"></div>

    <el-alert
      title="说明"
      type="info"
      :closable="false"
      description="此处配置将保存在浏览器 localStorage，并通过请求头传给后端（x-llm-api-key / x-llm-base-url / x-llm-model）。后端使用 OpenAI 兼容接口调用大模型。"
    />
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { http } from "../api/client";
import { loadLlmConfigFromStorage, setLlmConfigToStorage } from "../store/llmConfig";

const emit = defineEmits(["set-title"]);

const apiKey = ref("");
const baseUrl = ref("");
const model = ref("");
const testing = ref(false);
const provider = ref("qwen");

function loadFromStorage() {
  loadLlmConfigFromStorage();
  apiKey.value = localStorage.getItem("llm_api_key") || "";
  baseUrl.value = localStorage.getItem("llm_base_url") || "https://api.openai.com/v1";
  model.value = localStorage.getItem("llm_model") || "gpt-4o-mini";
}

function guessProviderByBaseUrl(url) {
  const u = (url || "").toLowerCase();
  if (u.includes("dashscope") || u.includes("qwen")) return "qwen";
  if (u.includes("groq")) return "groq";
  if (u.includes("localhost:1234")) return "lmstudio";
  if (u.includes("localhost:8000")) return "vllm";
  if (u.includes("api.openai.com")) return "openai";
  return "custom";
}

function applyProviderPreset(next) {
  if (next === "qwen") {
    baseUrl.value = "https://dashscope.aliyuncs.com/compatible-mode/v1";
    if (!model.value) model.value = "qwen-plus";
    return;
  }
  if (next === "openai") {
    baseUrl.value = "https://api.openai.com/v1";
    if (!model.value) model.value = "gpt-4o-mini";
    return;
  }
  if (next === "groq") {
    baseUrl.value = "https://api.groq.com/openai/v1";
    if (!model.value) model.value = "llama-3.1-8b-instant";
    return;
  }
  if (next === "lmstudio") {
    baseUrl.value = "http://localhost:1234/v1";
    return;
  }
  if (next === "vllm") {
    baseUrl.value = "http://localhost:8000/v1";
    return;
  }
}

function save() {
  setLlmConfigToStorage({
    apiKey: apiKey.value || "",
    baseUrl: baseUrl.value || "",
    model: model.value || ""
  });
  ElMessage.success("已保存");
}

function reset() {
  apiKey.value = "";
  baseUrl.value = "https://dashscope.aliyuncs.com/compatible-mode/v1";
  model.value = "qwen-plus";
  save();
}

async function test() {
  testing.value = true;
  try {
    save();
    const res = await http.post("/api/llm/test");
    if (res.data && res.data.ok) {
      ElMessage.success(res.data.message || "连通性测试成功");
    } else {
      const detail = res.data && res.data.message ? res.data.message : "连通性测试失败";
      const base = res.data && res.data.base_url ? `Base URL: ${res.data.base_url}` : "";
      const modelName = res.data && res.data.model ? `Model: ${res.data.model}` : "";
      ElMessage.error([detail, base, modelName].filter(Boolean).join("\n"));
    }
  } catch (e) {
    ElMessage.error("测试失败：请检查后端服务是否启动、Base URL/Key 是否可用");
  } finally {
    testing.value = false;
  }
}

onMounted(() => {
  emit("set-title", { title: "系统设置", sub: "大模型接入" });
  loadFromStorage();
  provider.value = guessProviderByBaseUrl(baseUrl.value);
});

watch(provider, (next) => {
  applyProviderPreset(next);
});
</script>
