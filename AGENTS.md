# AGENTS.md

本文件约束本仓库中的 AI Agent、自动化工具和开发者。所有改动必须真实、清晰、可运行、可审查。

## 1. 分支与 PR 流程

### 分支职责

```text
main     稳定演示分支，只接收 dev 的稳定版本 PR
dev      开发集成分支，默认接收所有功能 PR
feature  单一功能分支，从 dev 拉出并合入 dev
```

推荐合并路径：

```text
feature/* → dev → main
```

### 基本流程

```bash
git checkout dev
git checkout -b feature/<short-feature-name>
git add <files>
git commit -m "feat(scope): 描述具体修改"
git push origin feature/<short-feature-name>
# 创建 feature/* → dev 的 PR
```

### PR 粒度

- 每个 PR 只做一件事。
- 大功能必须拆成多个可审查 PR。
- 每个 PR 合并后，目标分支必须保持可运行。
- 禁止直接在 `main` 上开发功能。
- 禁止绕过 PR 直接合入 `main`。

## 2. PR 标题与描述

PR 标题必须清楚说明本次新增或修改内容，例如：

```text
feat(auth): 实现手机号验证码登录
```

所有 PR 必须使用 `.github/pull_request_template.md`，并完整填写：

- 标题
- 功能描述
- 实现思路
- 测试方式

创建 PR 前必须读取模板，不得使用空描述、单行描述或跳过任意 section。

## 3. Commit 规范

### 基本要求

- 每个 commit 对应一个清晰修改点。
- commit message 必须准确反映变更内容。
- 类型建议使用：`feat`、`fix`、`refactor`、`docs`、`test`、`chore`。

推荐格式：

```text
<type>(scope): <summary>
```

### 禁止事项

禁止使用空泛信息：

```text
update
fix
final
done
wip
all
提交
修改
完善
```

禁止以下行为：

- 一个 commit 混入多个不相关功能。
- 用 `docs` 提交代码功能。
- 用 `fix` 提交大规模重构。
- 用 `feat` 提交无关文件。
- 为了制造提交数量拆分无意义 commit。

## 4. 测试要求

新增核心逻辑时必须补充真实可运行的测试，优先覆盖：

- 正常输入
- 空输入
- 异常输入
- 边界条件
- 第三方 API 失败
- 文件不存在
- 配置缺失
- 权限不足
- 网络失败

禁止伪测试、表面测试或无法执行的测试。

## 5. 安全与密钥

禁止提交：

- API 密钥
- Token
- Cookie
- 私钥
- 数据库密码
- 个人账号凭证
- 真实用户隐私数据

配置文件要求：

- 真实配置放在 `.env` 或 `.env.local`。
- 示例配置放在 `.env.example`。
- `.env.example` 只能包含示例值。

示例：

```env
OPENAI_API_KEY=your_api_key_here
DATABASE_URL=your_database_url_here
```

## 6. PR 合并前检查

合并前必须确认：

- [ ] 本 PR 只做一件事。
- [ ] PR 标题清晰。
- [ ] PR 描述包含功能描述、实现思路、测试方式。
- [ ] PR 描述与实际代码变更一致。
- [ ] commit 分布合理。
- [ ] commit message 准确。
- [ ] 不存在无关文件变更。
- [ ] 不存在密钥或隐私数据。
- [ ] 新增核心逻辑已有测试。
- [ ] 测试真实运行过。
- [ ] 目标分支合并后仍可运行。
- [ ] README 是否需要同步更新已确认。

## 7. 仓库结构

推荐结构：

```text
.
├── frontend/
├── backend/
├── agents/
├── docs/
├── tests/
├── scripts/
├── README.md
├── AGENTS.md
└── .github/
    └── pull_request_template.md
```

要求：

- `frontend/` 和 `backend/` 分别说明启动方式。
- `agents/` 说明 Agent 工作流或提示词边界。
- `docs/` 存放设计文档。
- `tests/` 存放测试代码。
- `scripts/` 存放辅助脚本。
- `README.md` 必须能指导评审者完整运行项目。