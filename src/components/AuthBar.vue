<script setup>
import { useAuth } from '../lib/auth'
import { buildOAuthStartUrl } from '../lib/oauthStart'

const {
  isAuthenticated,
  displayName,
  planLabel,
  logout,
} = useAuth()

function handleGoogleLogin() {
  window.location.href = buildOAuthStartUrl('google')
}

async function handleLogout() {
  await logout()
}
</script>

<template>
  <div class="auth-bar">
    <template v-if="isAuthenticated">
      <span class="auth-user">
        <span class="auth-name">{{ displayName }}</span>
        <span class="plan-pill">{{ planLabel }}</span>
      </span>
      <button type="button" class="btn-auth ghost" @click="handleLogout">登出</button>
    </template>
    <button v-else type="button" class="btn-auth google" @click="handleGoogleLogin">
      <svg class="g-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
      </svg>
      <span class="login-label-full">Google 登入</span>
      <span class="login-label-short">登入</span>
    </button>
  </div>
</template>

<style scoped>
.auth-bar {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  flex-shrink: 0;
}

.auth-user {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  max-width: 12rem;
}

.auth-name {
  font-size: 0.82rem;
  color: var(--paper-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.plan-pill {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 0.12rem 0.4rem;
  border-radius: 999px;
  color: #041311;
  background: linear-gradient(135deg, var(--aqua), #5eead4);
  flex-shrink: 0;
}

.login-label-short { display: none; }

@media (max-width: 767px) {
  .auth-user {
    max-width: 7.5rem;
  }

  .auth-name {
    font-size: 0.78rem;
  }

  .login-label-full { display: none; }
  .login-label-short { display: inline; }
}
</style>
