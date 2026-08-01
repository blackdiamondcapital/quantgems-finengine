/** 與主站 www.quantgems.com 相同的方案判斷（選股需 Pro） */

export function normalizePlanKey(plan) {
  const key = String(plan ?? 'free').trim().toLowerCase()
  if (key === 'admin') return 'admin'
  if (key === 'enterprise' || key === 'prime') return 'prime'
  if (key === 'pro') return 'pro'
  if (key === 'lite_free') return 'lite_free'
  return 'free'
}

export function parseTrialEndDate(value) {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

export function resolveUserAccess(user) {
  if (!user || typeof user !== 'object') {
    return {
      tier: 'guest',
      effectivePlan: 'free',
      isLiteFree: false,
      isTrialActive: false,
      trialExpired: false,
      trialEndsAt: null,
      trialDaysLeft: null,
    }
  }

  const rawPlan = normalizePlanKey(user.plan)
  const sub = String(user.subscription_status ?? '').trim().toLowerCase()

  if (rawPlan === 'admin' || rawPlan === 'prime' || rawPlan === 'pro') {
    return {
      tier: rawPlan,
      effectivePlan: rawPlan,
      isLiteFree: false,
      isTrialActive: false,
      trialExpired: false,
      trialEndsAt: null,
      trialDaysLeft: null,
    }
  }

  if (rawPlan === 'free' && sub === 'active') {
    return {
      tier: 'pro',
      effectivePlan: 'pro',
      isLiteFree: false,
      isTrialActive: false,
      trialExpired: false,
      trialEndsAt: null,
      trialDaysLeft: null,
    }
  }

  const trialEnd = parseTrialEndDate(user.trial_end_date)
  const now = new Date()

  if (trialEnd) {
    if (trialEnd > now) {
      const msLeft = trialEnd.getTime() - now.getTime()
      const daysLeft = Math.max(0, Math.ceil(msLeft / (24 * 60 * 60 * 1000)))
      return {
        tier: 'trial_pro',
        effectivePlan: 'pro',
        isLiteFree: false,
        isTrialActive: true,
        trialExpired: false,
        trialEndsAt: trialEnd,
        trialDaysLeft: daysLeft,
      }
    }

    return {
      tier: 'lite_free',
      effectivePlan: 'lite_free',
      isLiteFree: true,
      isTrialActive: false,
      trialExpired: true,
      trialEndsAt: trialEnd,
      trialDaysLeft: 0,
    }
  }

  return {
    tier: 'free',
    effectivePlan: 'free',
    isLiteFree: false,
    isTrialActive: false,
    trialExpired: false,
    trialEndsAt: null,
    trialDaysLeft: null,
  }
}

export function getEffectivePlanKey(user) {
  return resolveUserAccess(user).effectivePlan
}

/** Pro 試用中／付費 Pro／Prime／Admin 才可使用選股（與主站一致） */
export function canUseScreener(user) {
  const plan = getEffectivePlanKey(user)
  return plan === 'pro' || plan === 'prime' || plan === 'admin'
}

export const SCREENER_LOGIN_REQUIRED_MESSAGE =
  '財務選股需先登入，且為 Pro 方案功能。'

export const SCREENER_PLAN_REQUIRED_MESSAGE =
  '財務選股需訂閱 Pro 版本才能使用，請前往主站方案頁升級。'
