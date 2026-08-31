# Windows 客户试用包契约

目标：发布 Windows 10/11 x64 解压即用的比赛试用 Beta。客户无需 Python、Node、Git、终端或 .env。
用户随后明确比赛上传用途：不扩展生产账号、隐私平台或部署体系，保留已经实现的基础本机隔离。
教程依据：第16章可复现交付、第12章离线验证、Extra09失败可观测；这些信息只存在开发仓库。
当前行为：仅源码和开发服务器，页面存在阶段编号、技术字段、英文状态。
允许修改：便携启动器、静态托管、发布脚本、客户文案和标签、测试、文档。
禁止修改：模型/Prompt/冻结业务Schema、权限/确认门禁、真实数据、密钥、模型费用授权、仓库可见性。
测试命令：发布专项 pytest、verify.ps1、独立解压包自带运行时 HTTP 冒烟及启动器自检。
人工确认点：真实模型效果、第二台物理电脑和生产身份未验收；保留 Beta，不冒称生产上线。

## 固定验收

- P01：根目录仅启动程序、使用说明、许可声明和内部资源；不带本项目教程、开发文档、测试或源码快照包。
- P02：内置官方 CPython 3.12.10 x64 嵌入版、锁定依赖和构建后的 Vue 页面；构建记录版本与散列。
- P03：单进程仅监听 127.0.0.1；不启用 reload/多worker，不开放API文档和教程元数据。
- P04：仅托管构建目录内的静态资源与允许的SPA路由；未知API、隐藏文件、路径穿越均404。
- P05：用户设置和工单/图片保存在 LocalAppData/SeaSon；更新软件不覆盖用户数据；退出启动器关闭子进程。
- P06：模型设置使用原生密码输入框，API Key按Windows当前用户DPAPI加密保存，不传入URL/命令行/日志。
- P07：默认AI未启用，人工工单可用；用户在本地启用并填写自己的密钥后重启应用，不为验证调用模型。
- P08：仅白名单构建应用文件，不复制.env、工作区data/uploads、Git、node_modules或开发者文档。
- P09：聊天/工单/图片/依据仅客户字段；枚举中文化，不显示Phase、HMAC、revision、Mock、工具函数名。
  风险、人工复核、未启用AI和未验证身份提示必须保留，不把显示名称冒充认证登录。
- P10：GitHub私有仓库发布v0.1.0-beta.1，提供ZIP和SHA256；不改仓库可见性、不自动合并PR。

## 许可与限制

hello-agents 0.2.9安装元数据标记CC-BY-NC-SA-4.0，完整许可与依赖原始声明随包保留；
本版仅内部非商业试用，不承诺商业分发许可。CPython嵌入版源自
https://www.python.org/downloads/release/python-31210/ ，使用方法依照
https://docs.python.org/3.12/using/windows.html#windows-embeddable 。
3.12.10是官方最后提供Windows二进制的3.12维护版，后续安全更新、应用签名及依赖漏洞修复仍为正式上线门禁。

## 维护者操作（不会进入客户包）

在已安装依赖的Windows x64工作区，先执行`verify.ps1`，提交干净分支后：

```powershell
.\.venv\Scripts\python.exe -m desktop.build_release --version v0.1.0-beta.1
.\.venv\Scripts\python.exe scripts/verify-windows-release.py <上一步输出的ZIP绝对路径>
```

产物位于忽略目录`release-output/版本-提交-随机标识/`，包含ZIP、SHA256SUMS.txt及独立包验证报告。
构建固定41个Python运行依赖，前端使用lockfile；CPython下载校验SHA256。每次新建目录，不覆盖旧包。
内部build-manifest.json记录源提交、dirty标记、组件版本、wheel散列和每个文件散列。
`--allow-dirty`只用于本地演练，正式GitHub上传必须使用`dirty_build=false`产物。
发布验证在系统临时目录重新解压，清空开发工具PATH，调用包内原生启动器与Python，并完成两类工单闭环。
测试数据和失败现场保留在报告所列临时目录，永不回填发行包。
