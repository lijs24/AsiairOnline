# Operations

## 当前状态

截至 2026-06-12，项目已经从备份脚本扩展为本地 ASIAIR 运维控制台。当前主要页面是 `/` 或 `/monitor-minterm`、`/camera`、`/mount`、`/materials`、`/advanced`；旧版 GPU 3D 赤道仪视图保留在 `/mount-classic`。

真实设备 IP、共享名和目标路径以 `config/devices.json` 为准。该文件被 git 忽略，不要把凭据写入仓库。

## 每日使用

常规检查：

```powershell
.\scripts\doctor.ps1
```

预演备份：

```powershell
.\scripts\backup-all.ps1
```

真实备份：

```powershell
.\scripts\backup-all.ps1 -Run
```

`-Run` 包装器会避开 19:00-06:00 拍摄窗口，并在真实备份结束后尝试触发素材库索引扫描。

只跑某台设备：

```powershell
.\scripts\backup-all.ps1 -Run -Device 90sap
```

查看最近结果：

```powershell
$env:PYTHONPATH = ".\src"
python -m asiairbridge status
```

## 首次确认共享路径

先列出 ASIAIR 暴露出来的 SMB 共享：

```powershell
.\scripts\discover.ps1
```

如果输出共享名和当前配置不同，把真实共享名写入 `config/devices.json` 的设备级 `source_roots`。

## 凭据处理

不要把密码写进项目文件。若 ASIAIR 共享需要 SMB 凭据，优先用 Windows Credential Manager 或 `cmdkey`：

```powershell
cmdkey /add:<device-ip> /user:<username> /pass:<password>
```

也可以在系统层建立持久连接：

```powershell
net use \\<device-ip> /persistent:yes
```

## 计划任务

安装每日自动备份：

```powershell
.\scripts\install-daily-task.ps1 -At 09:00
```

查看任务：

```powershell
Get-ScheduledTask -TaskName "AsiairBridge Daily Backup"
```

手动触发：

```powershell
Start-ScheduledTask -TaskName "AsiairBridge Daily Backup"
```

删除任务：

```powershell
Unregister-ScheduledTask -TaskName "AsiairBridge Daily Backup" -Confirm:$false
```

## 网页控制台

只在本机访问：

```powershell
.\scripts\start-web.ps1
```

同一 Tailscale 网络访问：

```powershell
.\scripts\start-tailnet-web.ps1
```

如果明确需要 tailnet 可写访问，才使用：

```powershell
.\scripts\start-web.ps1 -HostName 0.0.0.0 -AllowRemoteActions
```

查看本机 Tailscale IP：

```powershell
tailscale ip -4
```

开机登录后自动启动网页控制台：

```powershell
.\scripts\install-web-task.ps1
```

远程 tailnet 访问默认只读，可以查看状态、日志和素材库；写入动作需要服务端允许远程写入，并且相机控制还需要持有对应设备的 control lease。本机打开 `http://127.0.0.1:8787` 时仍可完整操作。

当前页面：

| 路径 | 页面 |
| --- | --- |
| `/` 或 `/monitor-minterm` | ops 总览页 |
| `/camera` | 相机预览与控制 |
| `/mount` | 赤道仪/星图遥测页 |
| `/materials` | 本地素材库 |
| `/advanced` | 高级 RPC 监测页 |
| `/mount-classic` | 旧版 GPU 3D 赤道仪视图 |

让 tailnet 只读控制台也在登录后自动恢复：

```powershell
.\scripts\install-tailnet-web-task.ps1
```

如果不想放开监听到所有网卡，也可以只在本机运行网页，再使用 Tailscale Serve 暴露给 tailnet：

```powershell
.\scripts\start-web.ps1
tailscale serve http://127.0.0.1:8787
```

## 排障

`doctor` 中 ping 失败但 TCP 成功：

设备可能禁止 ICMP，备份仍可能可用。以 TCP 和共享路径结果为准。

TCP 445 失败：

检查 Tailscale 是否在线、设备 IP 是否变化、Windows 防火墙或设备 SMB 服务是否可用。

共享路径失败：

运行 `.\scripts\discover.ps1`，确认共享名；必要时先在资源管理器打开 `\\设备IP`。

备份失败：

查看当天 `logs/` 下对应设备和源标签的 robocopy 日志，再查看 `state/latest.json` 的退出码。

出现锁文件：

`state/backup.lock` 表示已有备份正在运行。确认没有 Python 或 robocopy 进程后，可用：

```powershell
.\scripts\backup-all.ps1 -Run -ForceLock
```
