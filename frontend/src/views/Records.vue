<template>
  <div class="card">
    <div style="display:flex; gap:10px; align-items:center; justify-content:space-between;">
      <div style="font-weight:700;">文献管理</div>
      <el-button type="primary" @click="$router.push('/ocr')">新增入库</el-button>
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
        <el-button type="primary" @click="load">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </el-col>
    </el-row>

    <div style="height: 12px"></div>

    <el-table :data="items" border style="width: 100%" @row-dblclick="openEdit">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column prop="author" label="作者" width="120" />
      <el-table-column prop="dynasty" label="朝代" width="120" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="tags" label="标签" min-width="140" />
      <el-table-column prop="updated_at" label="更新时间" width="170" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="height: 12px"></div>

    <el-pagination
      background
      layout="total, prev, pager, next, sizes"
      :total="total"
      :page-size="pageSize"
      :current-page="page"
      @current-change="onPageChange"
      @size-change="onSizeChange"
    />
  </div>

  <el-drawer v-model="drawer" size="55%" :with-header="false">
    <div style="display:flex; align-items:center; justify-content:space-between;">
      <div style="font-weight:700;">记录编辑</div>
      <el-button @click="drawer=false">关闭</el-button>
    </div>
    <div style="height: 12px"></div>

    <el-form label-width="70px">
      <el-row :gutter="12">
        <el-col :span="8">
          <el-form-item label="标题">
            <el-input v-model="edit.title" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="作者">
            <el-input v-model="edit.author" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="朝代">
            <el-input v-model="edit.dynasty" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="12">
        <el-col :span="8">
          <el-form-item label="状态">
            <el-select v-model="edit.status" style="width:100%;">
              <el-option label="待校对" value="待校对" />
              <el-option label="待提取" value="待提取" />
              <el-option label="已入库" value="已入库" />
              <el-option label="需复核" value="需复核" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="16">
          <el-form-item label="标签">
            <el-input v-model="edit.tags" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="摘要">
        <el-input v-model="edit.summary" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" />
      </el-form-item>
      <el-form-item label="原文">
        <el-input v-model="edit.original_text" type="textarea" :autosize="{ minRows: 8, maxRows: 18 }" />
      </el-form-item>
      <el-form-item label="译文">
        <el-input v-model="edit.modern_translation" type="textarea" :autosize="{ minRows: 6, maxRows: 14 }" />
      </el-form-item>
    </el-form>

    <div style="display:flex; gap:10px;">
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      <el-button :loading="reloading" @click="reload">刷新</el-button>
      <el-button :loading="extracting" @click="reExtract">重新结构化提取</el-button>
    </div>
  </el-drawer>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { http } from "../api/client";

const emit = defineEmits(["set-title"]);

const filters = reactive({ keyword: "", status: "", dynasty: "" });
const items = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(10);

const drawer = ref(false);
const saving = ref(false);
const reloading = ref(false);
const extracting = ref(false);
const edit = reactive({
  id: null,
  title: "",
  author: "",
  dynasty: "",
  status: "",
  tags: "",
  summary: "",
  original_text: "",
  modern_translation: ""
});

async function load() {
  const skip = (page.value - 1) * pageSize.value;
  const res = await http.get("/api/records", {
    params: {
      skip,
      limit: pageSize.value,
      keyword: filters.keyword || undefined,
      status: filters.status || undefined,
      dynasty: filters.dynasty || undefined
    }
  });
  total.value = res.data.total || 0;
  items.value = res.data.items || [];
}

function resetFilters() {
  filters.keyword = "";
  filters.status = "";
  filters.dynasty = "";
  page.value = 1;
  load();
}

function onPageChange(p) {
  page.value = p;
  load();
}

function onSizeChange(s) {
  pageSize.value = s;
  page.value = 1;
  load();
}

async function openEdit(row) {
  const rid = row?.id || row;
  const res = await http.get(`/api/records/${rid}`);
  Object.assign(edit, res.data);
  drawer.value = true;
}

async function reload() {
  if (!edit.id) return;
  reloading.value = true;
  try {
    await openEdit(edit.id);
  } finally {
    reloading.value = false;
  }
}

async function save() {
  if (!edit.id) return;
  saving.value = true;
  try {
    await http.put(`/api/records/${edit.id}`, {
      title: edit.title,
      author: edit.author,
      dynasty: edit.dynasty,
      status: edit.status,
      tags: edit.tags,
      summary: edit.summary,
      original_text: edit.original_text,
      modern_translation: edit.modern_translation
    });
    ElMessage.success("已保存");
    drawer.value = false;
    load();
  } catch (e) {
    let msg = "保存失败";
    const resp = e && e.response;
    if (resp) {
      const detail =
        (resp.data && (resp.data.detail || resp.data.message || resp.data.error)) ||
        (typeof resp.data === "string" ? resp.data : "");
      msg = [msg, `${resp.status}`.trim(), detail].filter(Boolean).join("：");
    } else if (e && e.message) {
      msg = [msg, e.message].join("：");
    }
    ElMessage.error(msg);
  } finally {
    saving.value = false;
  }
}

async function reExtract() {
  if (!edit.id) return;
  extracting.value = true;
  try {
    const res = await http.post(`/api/records/${edit.id}/extract`, {
      chunk_size: 1200,
      max_chunks: 8
    });
    Object.assign(edit, res.data || {});
    ElMessage.success("已重新提取并更新记录");
    await load();
  } catch (e) {
    ElMessage.error("重新提取失败（请检查后端与大模型配置）");
  } finally {
    extracting.value = false;
  }
}

async function remove(row) {
  const rid = row.id;
  try {
    await ElMessageBox.confirm("确认删除该记录？", "删除确认", { type: "warning" });
    await http.delete(`/api/records/${rid}`);
    ElMessage.success("已删除");
    load();
  } catch (e) {
    return;
  }
}

onMounted(() => {
  emit("set-title", { title: "文献管理", sub: "CRUD 与检索" });
  load();
});
</script>
