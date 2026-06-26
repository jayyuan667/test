# 管理权限、导出、公共库快照与工序编辑修复设计

> 日期：2026-06-26  
> 分支：`yolo-react`  
> 类型：小范围 bugfix + 权限语义收口  
> 适用范围：管理后台、导出接口、数据库浏览、工艺生成页工序编辑

## 1. 背景

当前项目已完成认证、角色架构和数据隔离一期。最新用户反馈集中在 5 个问题：

1. 超级管理员给企业设置管理员权限的入口语义不清。
2. 工艺导出 XLSX 会失败，PDF 中文可能乱码。
3. 企业管理员看不到未分配用户，无法把新注册人员纳入本企业。
4. 超级管理员看不了公共库，数据库浏览快照图片空白。
5. 工艺生成最后编辑时，中间插入步骤前端显示异常；入库后数据库浏览出现空步骤。

本设计遵循 `PRODUCT.md` 的产品 UI 原则：少即是多、熟悉控件优先、权限边界可见、数据结果必须和用户看到的一致。

## 2. 非目标

- 不重做管理后台信息架构。
- 不引入审批、通知或申请流程。
- 不新增角色或认证模型。
- 不引入 react-router、shadcn 或新的设计系统。
- 不更换 PDF 导出引擎。
- 不修改工艺生成算法或 process_flow 数据契约。

## 3. 设计方案

### 3.1 管理员授权与未分配用户领取

#### 行为规则

- `super_admin` 拥有全局管理权限：
  - 可看全部企业、全部用户、未分配用户。
  - 可创建企业、停用企业。
  - 可把任意非超级管理员用户设置为企业管理员，并写入授权到期时间。
  - 可调整任意非超级管理员用户的企业归属和配额。
- `enterprise_admin` 只能管理本企业成员和未分配普通用户：
  - 可看本企业用户。
  - 可看 `role = user AND enterprise_id IS NULL` 的未分配用户池。
  - 可把未分配普通用户直接分配到自己的企业。
  - 不可看其他企业用户。
  - 不可修改任何用户角色。
  - 不可把用户分配到其他企业。
- `user` 不具备管理人员能力。

#### 前端交互

- 企业管理页中，超级管理员的按钮文案从“续期管理员”改为“设置/续期管理员”。
- 弹窗保留一个用户下拉和一个授权天数字段，不增加步骤条。
- 用户管理页中，企业管理员看到两个轻量筛选：
  - “本企业成员”
  - “未分配用户”
- 未分配用户行只显示一个主动作：“分配到本企业”。

#### 后端接口

- 复用 `GET /api/admin/users`：
  - 对 `super_admin`：保持全部或按 `enterprise_id` 过滤。
  - 对 `enterprise_admin`：支持 `scope=unassigned` 返回未分配普通用户；默认仍返回本企业用户。
- 复用 `PUT /api/admin/users/<user_id>`：
  - 对 `enterprise_admin`：仅允许把 `role=user AND enterprise_id IS NULL` 的用户更新为当前管理员的 `enterprise_id`。
  - 其他 `enterprise_id` 修改继续拒绝。

#### 架构偏移校验

- 不新增表。
- 不新增角色。
- 不改变 JWT Cookie、AuthContext 或现有 API 响应格式。
- 企业管理员仍不能跨企业读取或写入。

## 4. 导出修复

### 4.1 XLSX

当前导出实现运行时导入 `pandas`，但依赖清单未包含 pandas。修复方案是使用项目已有依赖 `openpyxl` 直接创建工作簿。

行为要求：

- 保持接口不变：`/api/export/<task_id>?format=xlsx`。
- 表头保持：`标签编码`、`工种`、`工序内容`。
- 支持当前 `process_flow.data` 和 `process_flow.tables` 两类数据。
- 空数据继续返回 404。
- 导出失败返回包含原因的 JSON 错误。

### 4.2 PDF

当前 PDF 用 PIL 绘制图片再保存 PDF，但字体候选只包含 Windows 字体，非 Windows 环境会回退到 PIL 默认字体，中文可能乱码。

字体候选按平台兼容补齐：

- Windows 优先：
  - `C:\Windows\Fonts\msyh.ttc`
  - `C:\Windows\Fonts\msyhbd.ttc`
  - `C:\Windows\Fonts\simsun.ttc`
  - `C:\Windows\Fonts\simhei.ttf`
- macOS fallback：
  - `/System/Library/Fonts/STHeiti Medium.ttc`
  - `/System/Library/Fonts/PingFang.ttc`
- Linux fallback：
  - `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`
  - `/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc`
  - `/usr/share/fonts/opentype/source-han-sans/SourceHanSansCN-Regular.otf`

行为要求：

- Windows 必须保持兼容。
- API 和数据库里继续使用 POSIX 风格 `/` 路径，落盘访问用 `os.path` / `pathlib` 转换。
- 找不到中文字体时，后端记录 warning，并返回明确错误或可诊断的降级结果，不能静默导出乱码。

#### 架构偏移校验

- 不新增大型导出依赖。
- 不更换 PDF 引擎。
- 不改变下载文件名和 MIME 类型。

## 5. 公共库与快照图片

### 5.1 超级管理员公共库可见

数据隔离一期规定：`super_admin` 默认不应无参数看到全平台私有数据。但公共库是平台级只读资源，超级管理员选择公共库时应直接可见。

修复规则：

- 当当前 scope 为 `scope_type = public` 时：
  - `super_admin` 可见公共库记录。
  - `enterprise_admin` 和已分配 `user` 可见公共库记录。
  - 未分配 `user` 可见公共库记录。
- 当当前 scope 非 public 时：
  - `super_admin` 仍需显式 `scope=all` 或 `enterprise_id=X` 才看全平台或指定企业私有数据。
  - 非超级管理员只能看本企业私有数据。

### 5.2 快照图片

数据库浏览快照来自库记录中的 `preview_task_id` 和 `preview_image_urls`。当前图片接口只按 task 权限校验，遇到 library preview 任务或旧记录时可能因 task_store 没有 task 而 404。

修复规则：

- 快照图片访问先证明用户能访问关联的库记录。
- 通过库记录可见性后，允许读取该记录关联的 `preview_task_id` 下的 asset。
- 文件路径必须继续做目录逃逸防护，不能允许 `..` 或绝对路径穿透。
- 如果找不到文件，返回 404，并在前端显示“快照文件不存在或已被清理”。

#### 架构偏移校验

- 不跳过企业隔离。
- 不把所有 result asset 公开。
- 不要求历史 library preview 任务必须补写 task_store 才能浏览。

## 6. 工艺生成页工序编辑

此问题定性为前端编辑态显示与状态同步 bug。

当前行为：

- 插入行时，`editRows` 增加一个空行。
- 渲染时过滤掉完全空白行。
- 用户看不到新行，无法输入。
- 入库时空行仍在 `editRows` 中，可能保存为空步骤。

修复设计：

- 编辑态显示使用未过滤的 `editRows`。
- 插入行后立即出现可编辑行。
- 空行只在最终提交边界清理：
  - 入库前。
  - 导出前。
  - 通知父组件 `onRowsChange` 前。
- 清理规则：
  - `code`、`trade`、`content` 全空的行丢弃。
  - 保留任一字段非空的行。
  - 保留行重新编号为 `0010`、`0020`、`0030`。

UI 要求：

- 不引入拖拽排序。
- 不引入复杂表格库。
- “+”按钮保持在行尾，仍表示“在下方插入”。
- 新空行应有可见输入态和 focus。
- 所有可编辑单元保留键盘可操作。

后端兜底：

- 库记录保存入口可过滤完全空白工序，防止旧前端或异常请求写入空步骤。
- 不改变 process row 的 `{ code, trade, content }` 结构。

#### 架构偏移校验

- 不改工艺生成算法。
- 不改 SSE 流式生成。
- 不改数据库 content 字段存储格式。

## 7. 前端设计规范

本轮只做局部修复，不重塑界面。

约束：

- 沿用现有 Tailwind + CSS variables。
- 使用现有按钮、表格、弹窗、select、toast 视觉语言。
- 每个屏幕只突出一个主动作。
- 表格行操作短文案，避免长按钮。
- 交互控件优先可见，不依赖 hover 才能发现关键能力。
- 点击目标尽量不小于 44px。
- 文本对比度满足 WCAG AA。
- loading、empty、error 状态在原位置显示。
- 动画只用于状态变化反馈，时长 150-250ms，并尊重 reduced motion。

#### 架构偏移校验

- 不引入新设计系统。
- 不引入全局路由。
- 不重做页面布局。
- 不把后台工具做成营销式视觉。

## 8. 验收标准

### 后端

- `super_admin` 可以通过现有授权入口设置/续期企业管理员。
- `enterprise_admin` 可以看到未分配普通用户，并能分配到自己企业。
- `enterprise_admin` 不能看到其他企业用户，不能分配到其他企业。
- XLSX 导出不依赖 pandas，能在 Windows/macOS/Linux 导出成功。
- PDF 导出在 Windows 使用中文字体，在 macOS/Linux 有 fallback。
- `super_admin` 选择公共库时可看到公共库记录。
- 快照 asset 不因 task_store 缺失而误 404，但仍不能越权访问其他企业记录。
- 空白工序不会被写入库记录。

### 前端

- 企业管理按钮文案清楚表达“设置/续期管理员”。
- 企业管理员用户页可切换“本企业成员 / 未分配用户”。
- 未分配用户行可以一键分配到本企业。
- 数据库浏览公共库在超级管理员下有记录时可见。
- 快照图片加载失败时有明确空状态，不是静默空白。
- 工艺生成页中间插入步骤后，新行立即显示且可编辑。
- 空插入行不出现在入库后的数据库浏览记录中。

### 测试

- pytest：
  - 管理员授权与企业管理员领取未分配用户。
  - 企业管理员跨企业管理被拒绝。
  - XLSX 导出成功且无需 pandas。
  - 公共库对 super_admin 可见。
  - 快照 asset 走库记录权限校验。
- Playwright：
  - 企业管理员领取未分配用户。
  - 超级管理员公共库可见。
  - 工序插入行可见、可编辑，空行不入库。
  - 导出按钮失败时显示明确错误。

## 9. 实施顺序建议

1. 后端权限与用户列表 scope。
2. 前端管理后台文案和未分配用户视图。
3. XLSX/PDF 导出修复。
4. 公共库查询与快照 asset 校验。
5. 工序编辑前端显示和提交清洗。
6. 回归测试与构建验证。
