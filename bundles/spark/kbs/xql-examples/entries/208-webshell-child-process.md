---
id: XQL-IR-208-webshell-child-process
title: Web server process spawning a shell (web shell exploitation) (T1190)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, alter, comp, sort]
attack: [T1190, T1505.003]
---

# Web server process spawning a shell (web shell exploitation) (T1190)

**Dataset**: `xdr_data`

Detects exploitation of a public-facing app: an IIS worker, Apache, Tomcat, or nginx process spawning a command interpreter -- the signature of a deployed web shell running OS commands. Group by parent+host to spot a single compromised server. Tune the web-server image list to your stack.

```sql
dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| alter web_parent = lowercase(actor_process_image_name)
| alter shell_child = lowercase(action_process_image_name)
| filter web_parent in ("w3wp.exe", "httpd.exe", "nginx.exe", "tomcat.exe", "java.exe", "php-cgi.exe")
| filter shell_child in ("cmd.exe", "powershell.exe", "pwsh.exe", "bash", "sh", "whoami.exe", "net.exe")
| comp count(action_process_image_command_line) as shell_cmds, values(shell_child) as children, values(actor_effective_username) as svc_account by web_parent, agent_hostname
| sort desc shell_cmds
```
