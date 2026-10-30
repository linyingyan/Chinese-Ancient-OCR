<template>
  <div class="card">
    <div style="display:flex; align-items:center; justify-content:space-between;">
      <div style="font-weight:700;">OCR校对与入库</div>
      <div>
        <el-button @click="loadSampleImage">载入示例图片</el-button>
        <el-button @click="loadSamplePdf">载入示例PDF</el-button>
      </div>
    </div>

    <div style="height: 12px"></div>

    <el-row :gutter="12">
      <el-col :span="8">
        <el-upload
          drag
          :auto-upload="false"
          :show-file-list="true"
          :on-change="onFileChange"
        >
          <div>拖拽文件到这里或点击上传</div>
          <div style="font-size:12px; color:#888; margin-top:6px;">支持 PNG/JPG/PDF</div>
        </el-upload>
        <div style="height: 10px"></div>
        <el-button type="primary" :loading="ocrLoading" @click="runOcr" :disabled="!file">
          执行OCR
        </el-button>
        <div style="height: 12px"></div>
        <el-form label-width="80px">
          <el-form-item label="OCR模式">
            <el-select v-model="ocrMode" style="width:100%;">
              <el-option label="质量优先" value="quality" />
              <el-option label="速度优先" value="fast" />
            </el-select>
          </el-form-item>
          <el-form-item label="PDF DPI">
            <el-input-number v-model="pdfDpi" :min="120" :max="400" :step="10" />
          </el-form-item>
        </el-form>
        <div style="height: 14px"></div>
        <el-form label-width="80px">
          <el-form-item label="来源名">
            <el-input v-model="sourceName" />
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="sourceType" style="width:100%;">
              <el-option label="图片" value="image" />
              <el-option label="PDF" value="pdf" />
            </el-select>
          </el-form-item>
          <el-form-item label="标签">
            <el-input v-model="tags" placeholder="逗号分隔" />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="status" style="width:100%;">
              <el-option label="待校对" value="待校对" />
              <el-option label="待提取" value="待提取" />
              <el-option label="已入库" value="已入库" />
              <el-option label="需复核" value="需复核" />
            </el-select>
          </el-form-item>
        </el-form>
      </el-col>

      <el-col :span="16">
        <el-tabs v-model="tab">
          <el-tab-pane label="OCR文本" name="text">
            <el-input
              v-model="text"
              type="textarea"
              :autosize="{ minRows: 16, maxRows: 26 }"
              placeholder="OCR输出或手动粘贴文本"
            />
            <div style="height: 10px"></div>
            <el-button type="primary" :loading="extractLoading" @click="extract" :disabled="!text.trim()">
              结构化提取/翻译
            </el-button>
          </el-tab-pane>
          <el-tab-pane label="提取结果" name="extract">
            <el-alert
              v-if="meta?.llm && !meta.llm.api_enabled"
              type="warning"
              :closable="false"
              title="当前未启用大模型（演示模式）"
              description="请到“系统设置”填写 API Key / Base URL / 模型名，否则现代译文与问答将无法得到真实结果。"
              show-icon
            />
            <div v-if="meta?.chunked" style="height: 10px"></div>
            <el-alert
              v-if="meta?.chunked"
              type="info"
              :closable="false"
              title="已启用长文本分段抽取"
              :description="`分段抽取：chunk_size=${meta.chunk_size}，max_chunks=${meta.max_chunks}`"
              show-icon
            />
            <div style="height: 10px"></div>
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form label-width="70px">
                  <el-form-item label="标题">
                    <el-input v-model="extraction.title" />
                  </el-form-item>
                  <el-form-item label="作者">
                    <el-input v-model="extraction.author" />
                  </el-form-item>
                  <el-form-item label="朝代">
                    <el-input v-model="extraction.dynasty" />
                  </el-form-item>
                </el-form>
              </el-col>
              <el-col :span="16">
                <el-form label-width="70px">
                  <el-form-item label="摘要">
                    <el-input v-model="extraction.summary" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" />
                  </el-form-item>
                </el-form>
              </el-col>
            </el-row>

            <el-form label-width="70px">
              <el-form-item label="译文">
                <el-input
                  v-model="extraction.modern_translation"
                  type="textarea"
                  :autosize="{ minRows: 6, maxRows: 12 }"
                />
              </el-form-item>
            </el-form>

            <div style="display:flex; gap:10px; align-items:center;">
              <el-button type="primary" :loading="saveLoading" @click="saveRecord" :disabled="!text.trim()">
                保存入库
              </el-button>
              <el-button @click="resetAll">清空</el-button>
            </div>

            <div style="height: 14px"></div>
            <el-collapse>
              <el-collapse-item title="实体列表" name="entities">
                <el-table :data="extraction.entities || []" border style="width: 100%">
                  <el-table-column prop="name" label="实体" />
                  <el-table-column prop="type" label="类型" width="120" />
                  <el-table-column prop="context" label="上下文" />
                </el-table>
              </el-collapse-item>
              <el-collapse-item title="三元组列表" name="triples">
                <el-table :data="extraction.triples || []" border style="width: 100%">
                  <el-table-column prop="subject" label="主体" />
                  <el-table-column prop="predicate" label="关系" width="140" />
                  <el-table-column prop="object" label="客体" />
                  <el-table-column prop="context" label="上下文" />
                </el-table>
              </el-collapse-item>
              <el-collapse-item title="原始JSON" name="json">
                <pre style="white-space: pre-wrap;">{{ JSON.stringify(extraction, null, 2) }}</pre>
              </el-collapse-item>
            </el-collapse>
          </el-tab-pane>

          <el-tab-pane label="批量OCR" name="batch_ocr">
            <el-row :gutter="12">
              <el-col :span="10">
                <el-upload
                  drag
                  multiple
                  :auto-upload="false"
                  :file-list="batchOcrFileList"
                  :on-change="onBatchOcrFileChange"
                  :on-remove="onBatchOcrFileRemove"
                >
                  <div>拖拽多个文件到这里或点击上传</div>
                  <div style="font-size:12px; color:#888; margin-top:6px;">支持 PNG/JPG/PDF（可多选）</div>
                </el-upload>
                <div style="height: 10px"></div>
                <el-form label-width="90px">
                  <el-form-item label="OCR模式">
                    <el-select v-model="batchOcrMode" style="width:100%;">
                      <el-option label="质量优先" value="quality" />
                      <el-option label="速度优先" value="fast" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="PDF DPI">
                    <el-input-number v-model="batchPdfDpi" :min="120" :max="400" :step="10" />
                  </el-form-item>
                </el-form>
                <el-button
                  type="primary"
                  :loading="batchOcrLoading"
                  :disabled="batchOcrFiles.length===0"
                  @click="runBatchOcr"
                >
                  开始批量OCR（{{ batchOcrFiles.length }}）
                </el-button>
              </el-col>
              <el-col :span="14">
                <el-alert
                  type="info"
                  :closable="false"
                  title="说明"
                  description="批量OCR完成后，可在右侧列表点击“载入”把某个结果导入到 OCR 文本区域，再进行结构化提取与入库。"
                  show-icon
                />
                <div style="height: 12px"></div>
                <el-table :data="batchOcrResults" border style="width: 100%" height="420">
                  <el-table-column prop="filename" label="文件名" min-width="180" />
                  <el-table-column label="长度" width="90">
                    <template #default="{ row }">{{ (row.text || '').length }}</template>
                  </el-table-column>
                  <el-table-column label="缓存" width="80">
                    <template #default="{ row }">{{ row.cached ? '是' : '否' }}</template>
                  </el-table-column>
                  <el-table-column label="操作" width="110">
                    <template #default="{ row }">
                      <el-button size="small" @click="loadBatchOcrResult(row)">载入</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </el-col>
            </el-row>
          </el-tab-pane>

          <el-tab-pane label="批量提取" name="batch">
            <el-row :gutter="12">
              <el-col :span="10">
                <el-form label-width="90px">
                  <el-form-item label="分段大小">
                    <el-input-number v-model="batchOptions.chunk_size" :min="300" :max="3000" :step="100" />
                  </el-form-item>
                  <el-form-item label="最大段数">
                    <el-input-number v-model="batchOptions.max_chunks" :min="1" :max="30" :step="1" />
                  </el-form-item>
                  <el-form-item label="强制分段">
                    <el-switch v-model="batchOptions.force_chunk" />
                  </el-form-item>
                </el-form>
              </el-col>
              <el-col :span="14">
                <el-alert
                  type="info"
                  :closable="false"
                  title="说明"
                  description="批量提取会对所选记录执行结构化抽取，并写回数据库（更新摘要/译文/structured_json，同时重建三元组与分段）。"
                  show-icon
                />
              </el-col>
            </el-row>

            <div style="height: 12px"></div>

            <el-row :gutter="12">
              <el-col :span="8">
                <el-input v-model="batchFilters.keyword" placeholder="关键词（标题/作者/原文/标签/来源）" clearable />
              </el-col>
              <el-col :span="4">
                <el-select v-model="batchFilters.status" placeholder="状态" clearable style="width:100%;">
                  <el-option label="待校对" value="待校对" />
                  <el-option label="待提取" value="待提取" />
                  <el-option label="已入库" value="已入库" />
                  <el-option label="需复核" value="需复核" />
                </el-select>
              </el-col>
              <el-col :span="4">
                <el-input v-model="batchFilters.dynasty" placeholder="朝代" clearable />
              </el-col>
              <el-col :span="8" style="display:flex; gap:10px;">
                <el-button type="primary" :loading="batchListLoading" @click="loadBatchList">查询</el-button>
                <el-button @click="resetBatchFilters">重置</el-button>
                <el-button
                  type="primary"
                  :loading="batchLoading"
                  :disabled="selectedRecordIds.length===0"
                  @click="runBatchExtract"
                >
                  批量提取（{{ selectedRecordIds.length }}）
                </el-button>
              </el-col>
            </el-row>

            <div style="height: 12px"></div>

            <el-table
              :data="batchItems"
              border
              style="width: 100%"
              @selection-change="onBatchSelectionChange"
            >
              <el-table-column type="selection" width="46" />
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="title" label="标题" min-width="180" />
              <el-table-column prop="author" label="作者" width="120" />
              <el-table-column prop="dynasty" label="朝代" width="120" />
              <el-table-column prop="status" label="状态" width="120" />
              <el-table-column prop="source_name" label="来源" min-width="160" />
              <el-table-column label="操作" width="110">
                <template #default="{ row }">
                  <el-button size="small" :loading="singleExtractingId===row.id" @click="extractOneRecord(row.id)">
                    提取
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <div style="height: 12px"></div>

            <el-pagination
              background
              layout="total, prev, pager, next, sizes"
              :total="batchTotal"
              :page-size="batchPageSize"
              :current-page="batchPage"
              @current-change="onBatchPageChange"
              @size-change="onBatchSizeChange"
            />
          </el-tab-pane>
        </el-tabs>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { http } from "../api/client";

const emit = defineEmits(["set-title"]);

const file = ref(null);
const ocrLoading = ref(false);
const extractLoading = ref(false);
const saveLoading = ref(false);

const tab = ref("text");

const sourceName = ref("");
const sourceType = ref("image");
const tags = ref("");
const status = ref("待校对");
const text = ref("");
const ocrMode = ref("quality");
const pdfDpi = ref(250);

const extraction = reactive({
  title: "",
  author: "",
  dynasty: "",
  summary: "",
  modern_translation: "",
  entities: [],
  triples: []
});
const meta = ref(null);

const batchOptions = reactive({ chunk_size: 1200, max_chunks: 8, force_chunk: false });
const batchFilters = reactive({ keyword: "", status: "", dynasty: "" });
const batchItems = ref([]);
const batchTotal = ref(0);
const batchPage = ref(1);
const batchPageSize = ref(10);
const selectedRecordIds = ref([]);
const batchListLoading = ref(false);
const batchLoading = ref(false);
const singleExtractingId = ref(null);
const batchLoadedOnce = ref(false);

const batchOcrFileList = ref([]);
const batchOcrFiles = ref([]);
const batchOcrResults = ref([]);
const batchOcrLoading = ref(false);
const batchOcrMode = ref("quality");
const batchPdfDpi = ref(250);

function onFileChange(uploadFile) {
  file.value = uploadFile.raw;
  sourceName.value = uploadFile.name;
  sourceType.value = uploadFile.name.toLowerCase().endsWith(".pdf") ? "pdf" : "image";
}

async function runOcr() {
  if (!file.value) return;
  ocrLoading.value = true;
  try {
    const form = new FormData();
    form.append("file", file.value);
    const res = await http.post(`/api/ocr?dpi=${pdfDpi.value}&mode=${ocrMode.value}`, form, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    text.value = res.data.text || "";
    tab.value = "text";
    ElMessage.success("OCR完成");
  } catch (e) {
    ElMessage.error("OCR失败");
  } finally {
    ocrLoading.value = false;
  }
}

function onBatchOcrFileChange(uploadFile, uploadFiles) {
  batchOcrFileList.value = uploadFiles;
  batchOcrFiles.value = uploadFiles.map((f) => f.raw).filter(Boolean);
}

function onBatchOcrFileRemove(uploadFile, uploadFiles) {
  batchOcrFileList.value = uploadFiles;
  batchOcrFiles.value = uploadFiles.map((f) => f.raw).filter(Boolean);
}

async function runBatchOcr() {
  if (batchOcrFiles.value.length === 0) return;
  batchOcrLoading.value = true;
  try {
    const form = new FormData();
    for (const f of batchOcrFiles.value) {
      form.append("files", f);
    }
    const res = await http.post(`/api/ocr/batch?dpi=${batchPdfDpi.value}&mode=${batchOcrMode.value}`, form, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    batchOcrResults.value = (res.data && res.data.items) || [];
    ElMessage.success(`批量OCR完成：${batchOcrResults.value.length} 个文件`);
  } catch (e) {
    ElMessage.error("批量OCR失败");
  } finally {
    batchOcrLoading.value = false;
  }
}

function loadBatchOcrResult(row) {
  text.value = row.text || "";
  sourceName.value = row.filename || "";
  const lower = (row.filename || "").toLowerCase();
  sourceType.value = lower.endsWith(".pdf") ? "pdf" : "image";
  tab.value = "text";
  ElMessage.success("已载入到 OCR 文本");
}

async function extract() {
  extractLoading.value = true;
  try {
    const res = await http.post("/api/extract", { text: text.value });
    const data = res.data || {};
    meta.value = data._meta || null;
    if (data && data._meta) delete data._meta;
    Object.assign(extraction, data);
    tab.value = "extract";
    ElMessage.success("提取完成");
  } catch (e) {
    ElMessage.error("提取失败");
  } finally {
    extractLoading.value = false;
  }
}

async function loadBatchList() {
  batchListLoading.value = true;
  try {
    const skip = (batchPage.value - 1) * batchPageSize.value;
    const res = await http.get("/api/records", {
      params: {
        skip,
        limit: batchPageSize.value,
        keyword: batchFilters.keyword || undefined,
        status: batchFilters.status || undefined,
        dynasty: batchFilters.dynasty || undefined
      }
    });
    batchTotal.value = res.data.total || 0;
    batchItems.value = res.data.items || [];
  } catch (e) {
    ElMessage.error("加载列表失败");
  } finally {
    batchListLoading.value = false;
  }
}

function resetBatchFilters() {
  batchFilters.keyword = "";
  batchFilters.status = "";
  batchFilters.dynasty = "";
  batchPage.value = 1;
  loadBatchList();
}

function onBatchSelectionChange(rows) {
  selectedRecordIds.value = (rows || []).map((r) => r.id);
}

function onBatchPageChange(p) {
  batchPage.value = p;
  loadBatchList();
}

function onBatchSizeChange(s) {
  batchPageSize.value = s;
  batchPage.value = 1;
  loadBatchList();
}

async function extractOneRecord(id) {
  singleExtractingId.value = id;
  try {
    await http.post(`/api/records/${id}/extract`, { ...batchOptions });
    ElMessage.success("已提取并写回记录");
    loadBatchList();
  } catch (e) {
    ElMessage.error("提取失败（请检查后端与大模型配置）");
  } finally {
    singleExtractingId.value = null;
  }
}

async function runBatchExtract() {
  batchLoading.value = true;
  try {
    const res = await http.post("/api/records/extract/batch", {
      record_ids: selectedRecordIds.value,
      ...batchOptions
    });
    ElMessage.success(`批量提取完成：成功 ${res.data.succeeded}，失败 ${res.data.failed}`);
    selectedRecordIds.value = [];
    loadBatchList();
  } catch (e) {
    ElMessage.error("批量提取失败");
  } finally {
    batchLoading.value = false;
  }
}

async function saveRecord() {
  saveLoading.value = true;
  try {
    const payload = {
      title: extraction.title || null,
      author: extraction.author || null,
      dynasty: extraction.dynasty || null,
      tags: tags.value || null,
      status: status.value,
      source_type: sourceType.value,
      source_name: sourceName.value || null,
      original_text: text.value,
      summary: extraction.summary || null,
      modern_translation: extraction.modern_translation || null,
      structured_json: { ...extraction }
    };
    await http.post("/api/records", payload);
    ElMessage.success("已入库");
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
    saveLoading.value = false;
  }
}

function resetAll() {
  file.value = null;
  sourceName.value = "";
  sourceType.value = "image";
  tags.value = "";
  status.value = "待校对";
  text.value = "";
  Object.assign(extraction, {
    title: "",
    author: "",
    dynasty: "",
    summary: "",
    modern_translation: "",
    entities: [],
    triples: []
  });
  meta.value = null;
  tab.value = "text";
}

async function loadSampleImage() {
  ElMessage.info("示例图片请在后端路径中上传到 OCR 识别，此前端暂不内置静态文件读取。");
}

async function loadSamplePdf() {
  ElMessage.info("示例PDF请在后端路径中上传到 OCR 识别，此前端暂不内置静态文件读取。");
}

onMounted(() => {
  emit("set-title", { title: "OCR校对", sub: "上传与校对" });
});

watch(tab, (value) => {
  if (value === "batch" && !batchLoadedOnce.value) {
    batchLoadedOnce.value = true;
    loadBatchList();
  }
});
</script>
