# Reporting and Quality Metrics

```bash
iot-ai-mc-gpt report --window 1d
iot-ai-mc-gpt report --window 7d
iot-ai-mc-gpt report --window 30d --format json
```

Every provider attempt may record requested/served model, request ID, auth route, input/cache/output/reasoning tokens, latency, retries, failure class, fallback, and rubric quality. Missing telemetry is `null`, never fabricated as zero. The included Excel workbook provides a dashboard template; a centralized web dashboard is roadmap work.
