# External assets and network dependencies

## Browser assets

TIME LOG serves its JavaScript, CSS, icons and Vazirmatn font files from the application origin. The font is bundled through `@fontsource/vazirmatn`; no Google Fonts or foreign JavaScript CDN is required. Keeping these assets local avoids adding a CDN availability dependency.

The optional ARCaptcha widget loads `https://nwidget.arcaptcha.ir/1/api.js`, an Iranian provider. It stays disabled unless deployment keys are configured. Google Sheets links open only when selected by the user. The Google Sheets API is a backend integration, not a replaceable asset CDN.

## Verification

`frontend/tests/e2e/local-assets.cjs` blocks all browser HTTP requests outside the application origin, signs in with a disposable local account, and visits nine application pages. It checks that font files load locally and records aggregate results under ignored `artifacts/audit/`. Set `QA_ASSET_USER` and `QA_ASSET_PASSWORD` through the environment; do not put real credentials in source. The target is restricted to local audit/demo ports 18082 and 18083. Run with ARCaptcha disabled; enabling it intentionally introduces a third-party widget dependency.

During the 2026-10-25 local check, all nine pages passed with zero external browser requests and six local font resources. The ARCaptcha script endpoint returned HTTP 200, but real challenge verification requires provider keys and was not certified. `lib.arvancloud.com` could not be reached from the test machine, so it was not substituted for working local assets. This is a connectivity observation, not a claim that the provider is generally unavailable.

## Build and optional service dependencies

Fresh Docker builds still need package and image repositories, including npm, PyPI, Docker images and upstream build sources. These are distinct from browser CDNs. `NPM_REGISTRY`, `PIP_INDEX_URL` and the documented Docker registry configuration can be supplied by an operator. A registry HTTP 401 challenge alone does not establish whether pinned images are available. No unverified mirror was made the default.

Google OAuth and Sheets endpoints cannot be replaced with an unrelated domestic CDN without changing the integration. Offline builds and Google Sheets delivery without internet access are not guaranteed.
