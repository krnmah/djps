/**
 * Smoke Test
 * ===================
 * Purpose  : Sanity-check that the API is alive and responding correctly.
 * VUs      : 1
 * Duration : 30 seconds
 * Pass     : All requests return 201, p95 < 500 ms, 0% errors.
 *
 * Run:
 *   docker compose --profile load run --rm k6 run /scripts/smoke.js
 */
import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.API_BASE_URL || "http://api:8000";

export const options = {
    vus: 1,
    duration: "30s",
    thresholds: {
        http_req_failed: ["rate<0.01"],
        http_req_duration: ["p(95)<500"],
    },
};

export default function () {
    const payload = JSON.stringify({
        payload: { task: "smoke-test", iteration: __ITER },
    });

    const res = http.post(`${BASE_URL}/jobs`, payload, {
        headers: { "Content-Type": "application/json" },
    });

    check(res, {
        "status is 201": (r) => r.status === 201,
        "has job id": (r) => JSON.parse(r.body).id !== undefined,
        "status is queued": (r) => JSON.parse(r.body).status === "queued",
    });

    sleep(1);
}
