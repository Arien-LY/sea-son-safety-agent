<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">安</span>
        <span><strong>海之子</strong><small>安全质量 Agent</small></span>
      </RouterLink>
      <span class="phase-chip">Phase 2 · 受控提案</span>
    </header>
    <main class="page"><slot /></main>
  </div>
</template>
