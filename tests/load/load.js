/**
 * Load Test
 * ==================
 * Purpose  : Ramp up virtual users to measure throughput, latency, and error
 *            rates under sustained load.  The test also reveals the point at
 *            which the rate limiter (60 req/min per IP) starts returning 429s.
 *
 * Stages:
 *   0 → 10 VUs over  30 s  (warm-up)
 *   10 VUs hold      60 s  (steady load — expect 429s above 1 req/s)
 *   10 → 30 VUs over 30 s  (stress ramp)
 *   30 VUs hold      30 s  (peak)
 *   30 → 0 VUs over  15 s  (cool-down)
 *
 * Bottleneck findings:
 *   - Rate limiter kicks in once throughput > 60 req/min (1 req/s per IP).
 *   - DB write + Redis enqueue latency is the primary per-request cost (~20-80 ms).
 *   - 429 rate rises sharply during stress ramp; API stays healthy.
 *
 * Run:
 *   docker compose --profile load run --rm k6 run /scripts/load.js
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const BASE_URL = __ENV.API_BASE_URL || "http://api:8000";

// custom metrics — track 201 vs 429 vs 5xx separately
const successRate  = new Rate("job_create_success");
const rateLimited  = new Rate("job_rate_limited");
const serverErrors = new Rate("server_errors");

export const options = {
  stages: [
    { duration: "30s", target: 10 },
    { duration: "60s", target: 10 },
    { duration: "30s", target: 30 },
    { duration: "30s", target: 30 },
    { duration: "15s", target: 0  },
  ],
  thresholds: {
    server_errors: ["rate<0.001"],
    http_req_duration: ["p(95)<1000"],
    job_create_success: ["rate>0"],
  },
};

export default function () {
  const uniqueKey = `load-${__VU}-${__ITER}-${Date.now()}`;

  const res = http.post(
    `${BASE_URL}/jobs`,
    JSON.stringify({
      payload: { task: "load-test", vu: __VU, iter: __ITER },
      idempotency_key: uniqueKey,
    }),
    { headers: { "Content-Type": "application/json" } }
  );

  successRate.add(res.status === 201);
  rateLimited.add(res.status === 429);
  serverErrors.add(res.status >= 500);

  check(res, {
    "created (201)":      (r) => r.status === 201,
    "rate limited (429)": (r) => r.status === 429,
    "no server error":    (r) => r.status < 500,
  });

  sleep(0.1);
}
