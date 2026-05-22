# OmniPOS Flutter frontend

Enterprise-style **feature-first** layout under `lib/`; backend lives in the OmniPOS repo root (Django), not inside this folder.

## API & auth

- Login calls `POST {baseUrl}api/token/` (JWT: `access` / `refresh`, or DRF-style `token`). **Wire this on the Django side** if not present yet.
- After tokens are stored, `GET api/accounts/user/profile/` loads the staff profile; routing uses `is_superuser`.
- Set `--dart-define=API_BASE_URL=https://your-api/` for release builds; otherwise the login form remembers the last host in secure storage.

```
lib/
  core/           # shared themes, network, routing (expand)
  features/
    auth/         # staff sign-in
    pos/          # counter / catalog
    inventory/
    accounting/
```

Run: `flutter run -d chrome` (web) or attach an Android/iOS device.
