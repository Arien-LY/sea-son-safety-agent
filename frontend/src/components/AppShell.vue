<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">安</span>
        <span><strong>海之子</strong><small>安全质量 Agent</small></span>
      </RouterLink>
      <nav class="main-nav" aria-label="主导航"><RouterLink to="/">咨询与上报</RouterLink><RouterLink to="/records">历史工单</RouterLink></nav>
    </header>
    <main class="page"><slot /></main>
  </div>
</template>

<style scoped>
.main-nav { display: flex; gap: 16px; font-weight: 700; }
.main-nav a { padding: 10px 0; }
.main-nav .router-link-exact-active { color: #1668e8; border-bottom: 2px solid #1668e8; }
@media (max-width: 480px) { .main-nav { gap: 12px; font-size: 13px; } .brand small { font-size: 10px; } }
</style>
