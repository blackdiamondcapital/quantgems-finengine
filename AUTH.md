# Google 登入（與主站相同）

本專案前端沿用 [www.quantgems.com](https://www.quantgems.com/) 的 Google OAuth（QuantGems Node + Passport，部署於 Render）。  
財報 API 本身不驗證 JWT；登入僅用於會員狀態顯示，功能可不登入使用。

## 前端環境變數

| 變數 | 說明 |
|------|------|
| `VITE_BACKEND_URL` | Auth 後端，預設 `https://taiwan-stock-returns-quantgems-vue-vercel.onrender.com` |
| `VITE_SITE_URL` | 正式站 origin（SSR／無 `window` 時的 fallback），如 `https://quantgems-finengine.vercel.app` |

實際 OAuth `redirect` 參數優先使用 `window.location.origin`。

localStorage 與主站相同：`quantgem_auth_token`、`quantgem_user`（不同 subdomain 不會自動共用）。

## 主站 redirect 白名單（必要）

在主站 Node／Render 後端允許下列 origin，否則 Google 登入 callback 會失敗：

- `https://quantgems-finengine.vercel.app`
- 本地開發（可選）：`http://localhost:5178`

此設定不在本 repo，需有主站後端權限者更新。
