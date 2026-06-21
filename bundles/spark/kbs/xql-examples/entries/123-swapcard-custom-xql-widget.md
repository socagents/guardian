---
id: XQL-123-7f5b258f
title: '- Swapcard - Custom XQL Widget'
category: investigation
dataset: bh_swapcard_raw
tags:
- alter
- comp
- limit
- sort
- view
ecosystem: xsiam
---
# - Swapcard - Custom XQL Widget

**Dataset**: `bh_swapcard_raw`

```sql
dataset = bh_swapcard_raw
| alter Platform = arrayindex(regextract(userAgent ,"(Windows NT [^;)\s]+|Mac OS X [^;)\s]+|iPhone OS [^;)\s]+|CPU OS [^;)\s]+|Android [^;)\s]+|iPad; CPU OS [^;)\s]+|CrOS [^;\)]+|Darwin/[0-9._]+|Linux|node|CFNetwork|NetworkingExtension|com\.apple\.WebKit\.Networking|symbolicator|Microsoft-WebDAV-MiniRedir|SkypeUriPreview)"),0)
| alter Browser = arrayindex(regextract(userAgent ,"(Chrome|Safari|Firefox|Edg|Opera|CriOS|MobileSafari|LinkedInBot|AhrefsBot|DuckDuckBot|DuckDuckGo|AdsBot-Google|Googlebot|YandexBot|PetalBot|Troy%20Events|curl|Go-http-client|undici|node|okhttp|symbolicator|NetworkingExtension|CFNetwork|com\.apple\.WebKit\.Networking|python-requests|Slackbot|Slackbot-LinkExpanding|axios|AASA-Bot|meta-externalagent|SkypeUriPreview|coccocbot-web|Microsoft-WebDAV-MiniRedir)"),0)
| alter useragent_short = if(concat(Platform , " ", Browser) = null, userAgent , concat(Platform , " ", Browser))
| comp count() as Counter by useragent_short
| sort desc Counter
| limit 20
| view graph type = column subtype = grouped layout = horizontal xaxis = useragent_short yaxis = Counter default_limit = `false` seriescolor("Counter","#01ec45")
```
