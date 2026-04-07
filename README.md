# Win11 丢包测试工具

一个面向 Windows 11 的桌面化丢包测试工具，使用 `Python + Tkinter` 构建，支持实时显示单次探测结果、丢包率、平均延迟、抖动趋势，并能导出 CSV 报表。

## 功能

- Win11 桌面 GUI，适合直接交给终端用户使用
- 双测试模式：传统 `ICMP Ping` 与更接近游戏同步流量的 `UDP 游戏发包`
- 支持输入域名或 IP，配置次数、间隔、超时和负载字节
- 支持连续测试，直到手动停止
- 内置 `UDP 回显服务`，两台机器都运行本工具即可做应用层高频发包测试
- UDP 模式支持配置目标端口和每轮突发包数，可模拟更密集的小包同步流量
- 实时统计已发送、已接收、丢包率、平均值、最小值、最大值、抖动
- 趋势图展示最近 60 次 RTT 变化，丢包点使用红色标记
- 导出 CSV，便于留档或发给网络运维
- GitHub Actions 自动构建 `PacketLossTester.exe`
- 打 tag 后自动把 exe 发布到 GitHub Release

## 本地运行

```powershell
cd C:\Users\Admin\projects\win11-packet-loss-tester
python main.py
```

## UDP 游戏发包模式怎么用

这个模式不是简单调用系统 `ping`，而是通过本工具自己的 UDP 报文头按序号持续发包，并等待对端原样回包，适合观察更接近在线游戏的数据面丢包和抖动。

推荐使用方式：

1. 在目标机器上启动本工具，切换到 `UDP 游戏发包` 模式。
2. 在窗口里的 `UDP 回显服务` 区域点击“启动回显服务”。
3. 记下目标机器的 IP 和监听端口。
4. 在测试机器上把测试模式切换到 `UDP 游戏发包`，填入目标 IP、UDP 端口、间隔和每轮突发包数。
5. 点击“开始测试”。

参数建议：

- `间隔(秒)` 设为 `0.02`，约等于 `50 包/秒`
- `每轮突发包数` 设为 `2` 到 `5`，可模拟更密集的同步帧
- `负载字节` 可按游戏业务包大小粗略设定，例如 `32`、`64`、`128`

说明：

- UDP 模式需要对端配合回包，否则会显示 `回包超时`
- 如果本机向未监听的本地 UDP 端口测试，可能显示 `端口不可达`
- 这是应用层 UDP 回显测试，更接近游戏网络行为，但不等于完整还原某个具体游戏协议

## 本地打包 EXE

```powershell
cd C:\Users\Admin\projects\win11-packet-loss-tester
python -m pip install --upgrade pip
pip install -r requirements-build.txt
pyinstaller --noconfirm packet_loss_tester.spec
```

生成结果位于：

```text
dist\PacketLossTester.exe
```

## GitHub Actions

工作流文件位于：

- `.github/workflows/build-exe.yml`

触发方式：

- 推送到 `main`
- 提交 PR 到 `main`
- 手动触发 `workflow_dispatch`
- 推送 `v*` tag 时，会在构建成功后自动上传 exe 到 Release

## 项目结构

```text
win11-packet-loss-tester/
├─ .github/workflows/build-exe.yml
├─ main.py
├─ packet_loss_tester.spec
├─ requirements-build.txt
├─ src/packet_loss_tester/
│  ├─ __init__.py
│  ├─ app.py
│  ├─ game_packet_service.py
│  ├─ ping_service.py
│  └─ probe_models.py
├─ tests/test_game_packet_service.py
└─ tests/test_ping_service.py
```

## 上传到 GitHub

如果本机已经配置好 Git 凭据，可以使用：

```powershell
git init
git branch -M main
git remote add origin https://github.com/<your-account>/win11-packet-loss-tester.git
git add .
git commit -m "feat: add win11 packet loss tester"
git push -u origin main
```

## 说明

- `ICMP Ping` 模式默认调用系统自带 `ping` 命令，不需要管理员权限
- `UDP 游戏发包` 模式使用 Python 标准库 `socket`，也不需要额外依赖
- GitHub Actions 固定使用 Python 3.13 打包，避免不同 runner 上的兼容性漂移
- CSV 使用 `utf-8-sig` 编码，Excel 直接打开不会乱码
