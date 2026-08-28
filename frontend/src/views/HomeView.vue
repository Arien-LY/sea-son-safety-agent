<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../api";
import type { RuntimeInfo } from "../types";

const runtime = ref<RuntimeInfo | null>(null);
const error = ref("");

onMounted(async () => {
  try {
    runtime.value = await api.getRuntime();
  } catch {
    error.value = "后端尚未启动";
  }
});
</script>

<template>
  <section class="hero">
    <div>
      <p class="eyebrow">施工现场问题闭环</p>
      <h1>安全、质量、管理与后勤问题，一个入口处理</h1>
      <p class="lead">
        当前是按 Hello-Agents V1.0.3 教程重新建立的干净仓库。先完成文字咨询和结构化分析，
        再逐步加入受控工作流、知识检索和图片识别。
      </p>
    </div>
    <div class="runtime-card">
      <span class="status-dot" :class="{ online: runtime }"></span>
      <div v-if="runtime">
        <strong>底座已连接</strong>
        <p>{{ runtime.tutorial_baseline }} · {{ runtime.framework }} {{ runtime.framework_version }}</p>
        <small>运行模式：{{ runtime.agent_mode }}</small>
      </div>
      <div v-else>
        <strong>{{ error || "正在检查后端" }}</strong>
        <p>启动 FastAPI 后会显示教程运行时信息。</p>
      </div>
    </div>
  </section>

  <section class="cards" aria-label="建设阶段">
    <article>
      <span>01</span><h2>文字咨询</h2><p>普通问答直接回复，专业问题输出结构化分析。</p>
    </article>
    <article>
      <span>02</span><h2>受控工作流</h2><p>人工确认后再创建记录，程序控制整改和复查状态。</p>
    </article>
    <article>
      <span>03</span><h2>知识与图片</h2><p>核心闭环稳定后，再加入有来源的依据和图片证据。</p>
    </article>
  </section>

  <section class="boundary">
    <h2>当前能力边界</h2>
    <p>本阶段尚未实现问题识别、图片分析或整改任务。页面只证明新仓库的前后端底座可以运行。</p>
  </section>
</template>

