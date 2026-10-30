<template>
  <div class="app-shell">
    <aside class="sidebar" :class="{ collapsed: isCollapsed }">
      <div class="sidebar-header">
        <div class="logo-badge">典</div>
        <div>
          <div class="logo-title">古籍智能系统</div>
          <div class="logo-sub">历史典籍结构化提取平台</div>
        </div>
      </div>
      <div class="sidebar-divider"></div>
      <div class="sidebar-menu-wrap">
        <el-menu
          :default-active="active"
          :collapse="isCollapsed"
          :collapse-transition="false"
          class="el-menu-vertical"
          background-color="transparent"
          text-color="#fff"
          active-text-color="#fff"
          router
        >
          <el-menu-item index="/">
            <el-icon><House /></el-icon>
            <span>首页</span>
          </el-menu-item>

          <el-sub-menu index="doc">
            <template #title>
              <el-icon><Collection /></el-icon>
              <span>典籍文献管理</span>
            </template>
            <el-menu-item index="/records">
              <el-icon><Notebook /></el-icon>
              <span>文献管理</span>
            </el-menu-item>
            <el-menu-item index="/export">
              <el-icon><Download /></el-icon>
              <span>数据导出</span>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="physical">
            <template #title>
              <el-icon><Document /></el-icon>
              <span>物理层提取</span>
            </template>
            <el-menu-item index="/ocr">
              <el-icon><Picture /></el-icon>
              <span>OCR校对与提取</span>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="relation">
            <template #title>
              <el-icon><Connection /></el-icon>
              <span>关联层计算</span>
            </template>
            <el-menu-item index="/graph">
              <el-icon><Share /></el-icon>
              <span>知识图谱展示</span>
            </el-menu-item>
            <el-menu-item index="/spacetime">
              <el-icon><Clock /></el-icon>
              <span>时空演变</span>
            </el-menu-item>
          </el-sub-menu>

          <el-menu-item index="/qa">
            <el-icon><ChatLineRound /></el-icon>
            <span>历史问题咨询</span>
          </el-menu-item>

          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </el-menu-item>
        </el-menu>
      </div>

      <button class="sidebar-toggle" type="button" @click="toggleCollapse" :aria-label="isCollapsed ? '展开侧边栏' : '折叠侧边栏'">
        <span class="sidebar-toggle-icon">
          <el-icon v-if="isCollapsed"><ArrowRightBold /></el-icon>
          <el-icon v-else><ArrowLeftBold /></el-icon>
        </span>
      </button>
    </aside>

    <section class="content">
      <div class="topbar">
        <div>
          <div class="topbar-title">{{ topTitle }}</div>
          <div class="topbar-sub">{{ topSub }}</div>
        </div>
        <div class="userpill">Admin User</div>
      </div>
      <main class="main">
        <router-view @set-title="onSetTitle" />
      </main>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import {
  ArrowLeftBold,
  ArrowRightBold,
  ChatLineRound,
  Clock,
  Collection,
  Connection,
  Document,
  Download,
  House,
  Notebook,
  Picture,
  Setting,
  Share
} from "@element-plus/icons-vue";

const route = useRoute();
const topTitle = ref("历史典籍内容结构化提取系统");
const topSub = ref("");

const isCollapsed = ref(false);

const active = computed(() => route.path);

function onSetTitle(payload) {
  topTitle.value = payload?.title || "历史典籍内容结构化提取系统";
  topSub.value = payload?.sub || "";
}

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value;
}
</script>

<style scoped>
.userpill {
  background: #f7f7f7;
  border: 1px solid rgba(0, 0, 0, 0.08);
  padding: 6px 10px;
  border-radius: 999px;
  color: #333;
  font-size: 12px;
}
.el-menu-vertical {
  border-right: none;
}
.el-menu-vertical :deep(.el-sub-menu__title),
.el-menu-vertical :deep(.el-menu-item) {
  border-radius: 12px;
  margin: 6px 6px;
  height: 44px;
  line-height: 44px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  transition: all 120ms ease-in-out;
}
.el-menu-vertical :deep(.el-sub-menu__title:hover),
.el-menu-vertical :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.10);
  border-color: rgba(255, 255, 255, 0.12);
  transform: translateX(1px);
}
.el-menu-vertical :deep(.el-menu-item.is-active) {
  background: rgba(255, 255, 255, 0.14) !important;
  border-color: rgba(255, 255, 255, 0.18) !important;
  box-shadow: 0 10px 18px rgba(0, 0, 0, 0.18);
}
.el-menu-vertical :deep(.el-menu-item.is-active)::before {
  content: "";
  position: absolute;
  left: 6px;
  top: 10px;
  width: 4px;
  height: 24px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.55);
}
.el-menu-vertical :deep(.el-icon) {
  margin-right: 10px;
}
.el-menu-vertical :deep(.el-menu-item.is-disabled) {
  opacity: 0.55;
}
</style>
