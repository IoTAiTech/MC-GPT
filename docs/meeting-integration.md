<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.5 | Date: 2026-08-08 -->
# Meeting, Calendar, PMD and Dashboard-Agent Integration

The Suite owns one meeting source of truth per configured Suite user scope. PMD and dashboard products integrate only through the authenticated `/api/meeting/v1` control plane; direct access to another product database is forbidden.

```bash
iot-ai meeting show MEETING_ID --view brief
iot-ai meeting show MEETING_ID --view complete
iot-ai meeting report --format xlsx --view brief --output meetings.xlsx
iot-ai meeting agent-register --surface pmd --agent-id security --display-name "PMD Security"
iot-ai meeting api-serve --host 127.0.0.1 --port 8790
```

Dashboard agents join as `agent:<surface>/<agent_id>` under a read-only consultation envelope. They receive no assignment, execution lease or write scope; a reply claiming any write is rejected. Cross-user or cross-host federation must use the authenticated API or signed exports rather than direct SQLite reads.
