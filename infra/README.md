# infra

**Owner:** P1 · Docker Compose stack: OpenTripPlanner 2 (transit), OSRM (car, motorcycle without toll roads), API. Image tags are pinned.

Infra targets live in `infra/Makefile`, which the root `Makefile` includes when present.

```bash
make up
make down
make logs
```
