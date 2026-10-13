# apps/mobile

**Owner:** P3 · Android app (Flutter stable, Riverpod, maplibre_gl, go_router, dio). Spec chapter 14.

Talks only to the API described in `contracts/openapi.yaml`; use `make mock` (Prism on :4010) until the backend is up. User-facing text is Bahasa Indonesia.

```bash
flutter analyze
flutter test
```

CI runs these once `pubspec.yaml` exists here.
