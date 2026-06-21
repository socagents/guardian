---
id: XQL-IR-240-large-outbound-exfil-over-web
title: Large outbound transfer to external web destination (T1048)
category: investigation
dataset: panw_ngfw_traffic_raw
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1048]
---

# Large outbound transfer to external web destination (T1048)

**Dataset**: `panw_ngfw_traffic_raw`

Scopes exfil-over-alternative-protocol by summing bytes sent to internet destinations and flagging asymmetric sessions where outbound dwarfs inbound (upload-heavy, the hallmark of data theft over web/cloud). Tune `total_sent_mb` to your normal upload baseline and tighten the `sent_to_recv_ratio` for noisier estates.

```sql
dataset = panw_ngfw_traffic_raw
| filter to_zone in ("internet", "untrust") and from_zone not in ("internet", "untrust")
| filter incidr(dest_ip, "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16") = false
| filter app in ("web-browsing", "ssl", "http-proxy", "google-base", "dropbox", "webdav")
| comp sum(bytes_sent) as bytes_out, sum(bytes_received) as bytes_in, count() as session_count, values(app) as apps by source_ip, dest_ip, source_user_info_name
| alter total_sent_mb = divide(bytes_out, 1048576)
| alter sent_to_recv_ratio = divide(bytes_out, bytes_in)
| filter total_sent_mb > 100 and sent_to_recv_ratio > 10
| sort desc total_sent_mb
```
