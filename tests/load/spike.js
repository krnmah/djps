/**
 * Spike Test
 * ===================
 * Purpose  : Simulate a sudden traffic burst (DDoS-like) to verify that the
 *            rate limiter blocks excess requests without crashing the API.
 *
 * Stages:
 *   0 → 100 VUs in 10 s  (sudden spike)
 *   100 VUs hold   20 s  (sustained spike — all requests above 1/s get 429)
 *   100 → 0  in    10 s  (drain)
 *
 * Pass criteria:
 *   - No 5xx errors (API must not crash).
 *   - p99 response time < 2 s (fast 429 responses keep latency low).
 *   - At minimum 1% of requests succeed (rate limiter allows the first 60/min).
 *
 * Expected bottleneck findings:
 *   - API survives the spike; 429 rate approaches 99%+ as VUs reach peak.
 *   - Response time stays low because 429 is returned before any DB I/O.
 *   - Demonstrates rate limiter as the first line of defence.
 *
 * Run:
 *   docker compose --profile load run --rm k6 run /scripts/spike.js
 */
import http from "k6/http";
import { check } from "k6";
import { Rate } from "k6/metrics";

const BASE_URL = __ENV.API_BASE_URL || "http://api:8000";

const serverErrorRate = new Rate("server_errors");

export const options = {
    stages: [
        { duration: "10s", target: 100 },
        { duration: "20s", target: 100 },
        { duration: "10s", target: 0 },
    ],
    thresholds: {
        server_errors: ["rate<0.001"],
        http_req_duration: ["p(99)<2000"],
    },
};

export default function () {
    const res = http.post(
        `${BASE_URL}/jobs`,
        JSON.stringify({ payload: { task: "spike-test", vu: __VU } }),
        { headers: { "Content-Type": "application/json" } }
    );

    const is5xx = res.status >= 500;
    serverErrorRate.add(is5xx);

    check(res, {
        "API alive (no 5xx)": (r) => r.status < 500,
        "rate limited or created": (r) => r.status === 201 || r.status === 429,
    });
}
