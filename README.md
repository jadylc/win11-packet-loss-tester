# Win11 丢包测试工具

一个面向 Windows 11 的桌面化丢包测试工具，使用 `Python + Tkinter` 构建，支持实时显示单次探测结果、丢包率、平均延迟、抖动趋势，并能导出 CSV 报表。

## 功能

- Win11 桌面 GUI，适合直接交给终端用户使用
- 支持输入域名或 IP，配置次数、间隔、超时和负载字节
- 支持连续测试，直到手动停止
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
│  └─ ping_service.py
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

- 程序默认调用系统自带 `ping` 命令，不需要管理员权限
- GitHub Actions 固定使用 Python 3.13 打包，避免不同 runner 上的兼容性漂移
- CSV 使用 `utf-8-sig` 编码，Excel 直接打开不会乱码
