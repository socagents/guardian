---
id: XQL-121-7f5b258f
title: '- Swapcard - Custom XQL Widget'
category: investigation
dataset: bh_swapcard_raw
tags:
- alter
- comp
- fields
- filter
- sort
- view
ecosystem: xsiam
---
# - Swapcard - Custom XQL Widget

**Dataset**: `bh_swapcard_raw`

```sql
dataset = bh_swapcard_raw // | fields suspected*
| filter (`SUSPECTED_BOT` not in (null, """"""))
| alter Platform = arrayindex(regextract(userAgent ,"(Windows NT [^;)\s]+|Mac OS X [^;)\s]+|iPhone OS [^;)\s]+|CPU OS [^;)\s]+|Android [^;)\s]+|iPad; CPU OS [^;)\s]+|CrOS [^;\)]+|Darwin/[0-9._]+|Linux|node|CFNetwork|NetworkingExtension|com\.apple\.WebKit\.Networking|symbolicator|Microsoft-WebDAV-MiniRedir|SkypeUriPreview)"),0)
| alter Browser = arrayindex(regextract(userAgent ,"(Chrome|Safari|Firefox|Edg|Opera|CriOS|MobileSafari|LinkedInBot|AhrefsBot|DuckDuckBot|DuckDuckGo|AdsBot-Google|Googlebot|YandexBot|PetalBot|Troy%20Events|curl|Go-http-client|undici|node|okhttp|symbolicator|NetworkingExtension|CFNetwork|com\.apple\.WebKit\.Networking|python-requests|Slackbot|Slackbot-LinkExpanding|axios|AASA-Bot|meta-externalagent|SkypeUriPreview|coccocbot-web|Microsoft-WebDAV-MiniRedir)"),0)
| alter useragent_short = if(concat(Platform , " ", Browser) = null, userAgent , concat(Platform , " ", Browser))
| alter SUSPECTED_BOT_value = SUSPECTED_BOT -> value
| comp count() as counter by SUSPECTED_BOT_value , useragent_short
| sort desc counter
// | view column order = populated
| view graph type = column subtype = stacked layout = horizontal show_callouts_names = `true` xaxis = SUSPECTED_BOT_value yaxis = counter series = useragent_short seriescolor("Other","#01ec45")
```
